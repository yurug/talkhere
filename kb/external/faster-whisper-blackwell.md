---
id: external-faster-whisper-blackwell
type: external
summary: Runtime behaviour of faster-whisper/CTranslate2 on the RTX 5060 Ti (Blackwell sm_120) — version matrix, the float16-not-int8 gotcha, model choice, and CPU fallback.
domain: external-dependency
last-updated: 2026-07-03
related: [arch-0001, properties-non-functional]
---
# faster-whisper on Blackwell (RTX 5060 Ti, sm_120)

**Status: researched 2026-07-03, not yet verified on-device.** Step 1 of the plan
verifies these claims empirically; treat them as the hypothesis to confirm/refute.

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
| Component | Minimum | Why |
|-----------|---------|-----|
| NVIDIA driver / CUDA runtime | **CUDA 12.8+** | CUDA ≤ 11.8 tops out at sm_90; sm_120 needs 12.8 |
| cuDNN | **9.x** | CTranslate2 ≥ 4.5.0 links cuDNN 9 (needs CUDA ≥ 12.3) |
| CTranslate2 | **≥ 4.5.0** | earlier builds lack sm_120 / crash on new tensor-core padding |
| faster-whisper | recent (pulls CT2 ≥ 4.5) | — |

Install shape (to confirm in Step 1): a venv with `pip install faster-whisper`, ensuring
the CTranslate2 wheel is ≥ 4.5.0 and CUDA 12.8 libs are visible. cuDNN 9 libs must be on
the loader path (common failure: `libcudnn_ops.so.9 not found`).

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
> Load the model ONCE per process, but talkhere is short-lived per utterance, so model
> load time (seconds) would dominate latency. Mitigation options to decide in Step 1:
> (a) accept per-invocation load with a small/turbo model; (b) a tiny persistent
> "transcriber" helper process the STOP path talks to; (c) keep model warm via an
> optional `--serve` mode. Measure first (NF1) before adding complexity.

## Sources
- SYSTRAN/faster-whisper (GitHub), issues #1086 #1401 on CUDA/CT2 versions.
- SubtitleEdit #10180: "Faster Whisper crashes on RTX 50-series (cuBLAS NOT_SUPPORTED) unless float16".
- whisperX #1211 and whisperx-blackwell (Mekopa) on sm_120 workarounds (arch spoofing).
- pluja/whishper #172: CUDA 12.8 / PyTorch 2.7+ for Blackwell.

## Related files
- `architecture/decisions/0001-pluggable-stt-local-default.md` — the fallback ladder.
- `external/openai-transcription-api.md` — the guaranteed-works fallback.
