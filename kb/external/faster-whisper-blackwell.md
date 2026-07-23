---
id: external-faster-whisper-blackwell
type: external
summary: Verified runtime of faster-whisper/CTranslate2 on the RTX 5060 Ti (Blackwell sm_120) — exact versions, the float16-not-int8 gotcha, the cuBLAS+cuDNN pip+LD_LIBRARY_PATH recipe, measured latency, model choice, CPU fallback.
domain: external-dependency
last-updated: 2026-07-23
related: [arch-0001, properties-non-functional]
---
# faster-whisper on Blackwell (RTX 5060 Ti, sm_120)

**Status: VERIFIED on pangoline 2026-07-08.** float16 `large-v3-turbo` loads and
transcribes correctly on the GPU (jfk.wav → exact ground-truth text, lang=en p=0.96).
Verified stack: driver **580.105.08** (CUDA 13.0-capable), **ctranslate2 4.8.1**,
**faster-whisper 1.2.1**, **nvidia-cudnn-cu12 9.24**, **nvidia-cublas-cu12 12.9**.

### Measured latency (jfk.wav, 11 s audio, model in HF cache)
- model load: **2.23 s** · transcribe: **2.59 s** (≈4× real-time).
- ⇒ per-invocation stop→text ≈ **load 2.2 s + transcribe ~1.3 s (for a 5 s clip) ≈ 3.5 s**;
  warm (model resident) ≈ **1.3 s** (beats NF1 ≤2 s). This is the Q5 datum: per-invocation
  is usable, a `--serve` warm helper is snappy. v1 default = per-invocation (no daemon).

### Measured VRAM footprint — and why the GPU being *shared* matters (2026-07-23)
`large-v3-turbo` / float16 holds **~1920 MiB** during inference (`nvidia-smi
--query-compute-apps`), of which roughly 1.6 GB is the loaded model and the rest is the
inference workspace. The consequence on a workstation whose GPU also runs ollama /
llama.cpp / games: with free VRAM *between* those two numbers, `WhisperModel(...)`
**succeeds** and the transcription then dies with `CUDA failed with error out of memory`.
The log signature is a `loaded … in N s` line with no `transcribed` line after it.

CTranslate2 surfaces this as a plain exception from `model.transcribe(...)`, so it must be
caught around the *inference*, not only around the load (talkhere: E5/E16 — pre-flight
`nvidia-smi --query-gpu=memory.free` against `TALKHERE_MIN_VRAM_MB`, default 2300 MiB, then
retry on cpu). CPU/int8 for the same model runs ≈1.2× real time (115 s for a 98 s
utterance) — slow, but it returns text.

## Why faster-whisper over openai-whisper / whisper.cpp here
- `faster-whisper` = CTranslate2 reimplementation of Whisper: 4× faster, lower VRAM,
  clean Python API (`WhisperModel(...).transcribe(wav)`), batching. Best Python fit for a
  KISS script.
- `openai-whisper` needs PyTorch; **PyTorch stable lacks sm_120 kernels** for Blackwell
  (would need a nightly cu128 build) → avoid for the default path.
- `whisper.cpp` is the robust plan-B: single binary, CUDA **or** Vulkan **or** CPU, and a
  `--stream` mode. If CTranslate2 fights Blackwell, wrap the `whisper-cli` binary as a
  third backend. Not built in v1 unless Step 1 forces it.

## Version matrix required for sm_120 (Blackwell)
| Component | Minimum / verified | Why |
|-----------|--------------------|-----|
| NVIDIA driver | 580.x (CUDA 12.8+/13.0) | CUDA ≤ 11.8 tops out at sm_90; sm_120 needs 12.8+ |
| CTranslate2 | ≥ 4.5.0 (**used 4.8.1**) | earlier builds lack sm_120 / crash on new tensor-core padding |
| faster-whisper | **1.2.1** | pulls CT2; clean `WhisperModel` API |
| nvidia-cudnn-cu12 | 9.x (**9.24**) | CT2 needs cuDNN 9 (`libcudnn_ops.so.9`) |
| nvidia-cublas-cu12 | 12.x (**12.9**) | CT2 needs `libcublas.so.12` — a SEPARATE pip pkg, NOT bundled |

### Install + launch recipe (the two non-obvious failures, both hit + solved)
`pip install faster-whisper nvidia-cudnn-cu12 nvidia-cublas-cu12` in a venv. Neither the
driver nor a CUDA toolkit is required (no `nvcc`); the pip wheels carry the runtime.
**But** CTranslate2 dlopens cuDNN/cuBLAS at model-load and does NOT find the pip-installed
libs on its own — the process MUST run with those dirs on `LD_LIBRARY_PATH`:
```
LD_LIBRARY_PATH="$(python -c "import glob,sysconfig,os;\
print(':'.join(glob.glob(os.path.join(sysconfig.get_paths()['purelib'],'nvidia','*','lib'))))")"
```
Failure signatures seen without it: `Library libcublas.so.12 is not found or cannot be
loaded` (missing cuBLAS pkg or path); analogous `libcudnn_ops.so.9`. talkhere's LocalBackend
sets this env from its own venv before importing faster_whisper.

## THE gotcha: use float16, not int8
On RTX 50-series, `compute_type="int8"` / `int8_float16` **crashes** with
`cuBLAS ... NOT_SUPPORTED` — the INT8 tensor cores need padding absent in older CT2.
**Use `compute_type="float16"`.** This is why `TALKHERE_COMPUTE` defaults to `float16`
and the code overrides int8→float16 on cuda (E6). float16 on 16 GB VRAM easily fits
`large-v3` / `large-v3-turbo`.

## Model choice
- Default **`large-v3-turbo`** (a.k.a. distil-large turbo): near-large-v3 accuracy, much
  faster — ideal for short interactive dictation, strong FR + EN.
- Alternatives via `TALKHERE_MODEL`: `large-v3` (max accuracy), `medium`/`small` (lower
  latency / CPU fallback). First use downloads weights to the HF cache (network once).

## API call shape
```python
from faster_whisper import WhisperModel
model = WhisperModel(MODEL, device="cuda", compute_type="float16")   # cache the object
segments, info = model.transcribe(
    wav_path,
    language=None if lang == "auto" else lang,   # P4
    initial_prompt=vocab_or_None,                # ~/.talkhere.prompt (T9)
    vad_filter=True,                             # trims silence, helps T2
    condition_on_previous_text=False,            # reduce silence hallucination (T2)
)
text = "".join(s.text for s in segments).strip()
```
`transcribe` is **lazy**: it returns a generator; nothing runs until you iterate
`segments`. Iterate fully before timing/latency claims (NF1).

## CPU fallback (pangolin / cuda failure)
`device="cpu", compute_type="int8"` is fine on CPU (the int8 crash is GPU-specific).
Use a smaller model (`small`/`medium`) on CPU to keep latency sane.

## Agent notes
> **Model-load decision (Q5), now measured:** load is ~2.2 s, transcribe ~1.3 s for a 5 s
> clip. v1 default is **per-invocation load** (no daemon, ~3.5 s stop→text) — simplest and
> honours NF2. A `--serve` warm helper (model resident, ~1.3 s) is the documented upgrade
> for anyone wanting sub-2 s; design LocalBackend so the model-load and transcribe steps are
> separable so `--serve` can reuse them. Do NOT add the helper in v1 unless the user asks.

## Sources
- SYSTRAN/faster-whisper (GitHub), issues #1086 #1401 on CUDA/CT2 versions.
- SubtitleEdit #10180: "Faster Whisper crashes on RTX 50-series (cuBLAS NOT_SUPPORTED) unless float16".
- whisperX #1211 and whisperx-blackwell (Mekopa) on sm_120 workarounds (arch spoofing).
- pluja/whishper #172: CUDA 12.8 / PyTorch 2.7+ for Blackwell.

## Related files
- `architecture/decisions/0001-pluggable-stt-local-default.md` — the fallback ladder.
- `external/openai-transcription-api.md` — the guaranteed-works fallback.
