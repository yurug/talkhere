# talkhere

**Talk-to-type for Linux/X11.** Press a hotkey, speak, press it again — the recognised text
is typed at the cursor of whatever window has focus: terminal, editor, browser, chat, any
X11 app. No dictation window, no copy-paste dance. Transcription runs **locally on your GPU**
by default (private, offline, no per-use cost), with CPU and OpenAI-API fallbacks.

It's the spoken-input sibling of [revisor](https://github.com/yurug/revisor): same KISS
spirit — one script, one job, done well.

```
  $mod+t        ●  speak…              $mod+t        "…types here"
 ───────────▶  recording  ───────────────────────▶  text at your cursor
```

## Features

- **Types anywhere** — injects into the focused window via `xdotool`; works in terminals,
  Emacs/Vim, browsers, chat apps. Unicode-safe (accents, em-dashes, emoji verified).
- **Single toggle hotkey** — press to start, press to stop. No daemon; zero footprint when idle.
- **Local by default** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on an
  NVIDIA GPU. Your audio never leaves the machine.
- **Graceful fallbacks** — GPU → CPU → OpenAI API, chosen automatically or pinned per run.
- **Bilingual** — auto-detects language, or force it (`--lang fr`). Optional vocabulary file
  biases spelling of names/jargon.
- **Fails safe** — silence or an accidental double-tap types nothing; every error notifies you.

## Requirements

- **Linux with X11** (Wayland is out of scope for now — it relies on `xdotool`). Any window
  manager; i3 is what the hotkey examples use.
- **Python 3.11+**, a **microphone**, and one of:
  - an **NVIDIA GPU** with a recent driver (CUDA 12.8+ capable) for the local backend, **or**
  - an **OpenAI API key** for the API backend (no GPU needed), **or**
  - just a CPU (slower, but works).
- System tools: `xdotool` (typing), `xclip` (clipboard sink), an audio recorder
  (`pw-record` from PipeWire, or `arecord` from ALSA), and optionally `notify-send`/`paplay`
  for cues.

## Install

```bash
# 1. System tools (Debian/Ubuntu example)
sudo apt-get install -y xdotool xclip pipewire-bin libnotify-bin pulseaudio-utils
#   (alsa-utils provides `arecord` as an audio fallback)

# 2. The tool + Python deps in a venv
git clone https://github.com/yurug/talkhere.git
cd talkhere
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # local GPU backend (faster-whisper + cuDNN/cuBLAS)

# 3. Put the launcher on your PATH
ln -s "$PWD/bin/talkhere" ~/.local/bin/talkhere
```

The `bin/talkhere` wrapper runs the tool from its own venv, so it works from any context
(shell, hotkey). First use of the local backend downloads the Whisper model (~1.6 GB) to the
Hugging Face cache. **No CUDA toolkit is required** — the pip wheels carry the runtime, and
talkhere loads cuDNN/cuBLAS itself (see [Backends](#backends)).

**No GPU?** Skip the heavy wheels and use the API backend:
```bash
.venv/bin/pip install --no-deps -r requirements.txt   # or just skip requirements entirely
export OPENAI_API_KEY=sk-...      # the API backend needs only curl + this key
talkhere --backend api --once 4
```

### Bind a hotkey (i3 example)

```
# ~/.config/i3/config
bindsym $mod+t       exec --no-startup-id "$HOME/.local/bin/talkhere; pkill -RTMIN+4 i3blocks"
bindsym $mod+Shift+t exec --no-startup-id "$HOME/.local/bin/talkhere --cancel; pkill -RTMIN+4 i3blocks"
```
Reload i3 (`$mod+Shift+r`). On other WMs, bind `talkhere` (toggle) and `talkhere --cancel`
to whatever keys you like. The optional `pkill -RTMIN+4 i3blocks` refreshes an i3blocks mic
indicator — see [`i3blocks/`](#optional-i3blocks-indicator) below; drop it if you don't use i3blocks.

## Usage

Normal use is the toggle: **press the hotkey, speak, press it again.** A cue confirms start;
the text appears at your cursor a moment after you stop. The cancel key discards a recording.

For scripting or one-shots there's a CLI (`talkhere --help`):

| Command | What it does |
|---|---|
| `talkhere` | **toggle** — start recording if idle, else stop → transcribe → type |
| `talkhere --cancel` | abort an in-progress recording, type nothing |
| `talkhere --stop` | force-stop + transcribe (e.g. a second binding) |
| `talkhere --once N` | record N seconds then transcribe (no toggle; handy for scripts) |
| `talkhere --lang fr` | force French (or `en`) for this utterance |
| `talkhere --backend api` | use the OpenAI API instead of the local GPU |
| `talkhere --sink clipboard` | put the text on the clipboard instead of typing it |
| `talkhere --status` | print `idle`/`recording` (exit 0/1) — for status bars |
| `talkhere -v ...` | also echo the transcript to stdout |

## Configuration

Precedence: **command-line flag → environment variable → config file → built-in default.**

**Config file** — `~/.config/talkhere/config.toml` (all keys optional):
```toml
backend = "local"          # local | api
sink = "type"              # type | paste | clipboard
lang = "auto"              # auto | fr | en
trailing_space = true      # append one space so consecutive dictations don't run together
[local]
model = "large-v3-turbo"   # any faster-whisper model
device = "cuda"            # cuda | cpu  (falls back to cpu on cuda failure)
compute_type = "float16"   # keep float16 on NVIDIA 50-series (int8 crashes there)
[api]
model = "whisper-1"
[sink.type]
key_delay_ms = 8           # xdotool inter-key delay (0 can drop chars)
[sink.paste]
paste_key = "ctrl+v"       # per-app paste chord (e.g. ctrl+shift+v in terminals)
```

**Environment variables:** `TALKHERE_BACKEND`, `TALKHERE_SINK`, `TALKHERE_LANG`,
`TALKHERE_MODEL`, `TALKHERE_DEVICE`, `TALKHERE_COMPUTE`, `TALKHERE_API_MODEL`,
`TALKHERE_TRAILING_SPACE`, `TALKHERE_KEEP_WAV`.

**OpenAI key** (API backend): `OPENAI_API_KEY`, else a GNOME keyring entry — by default
`service=talkhere key=api-key`, overridable with `TALKHERE_KEYRING_SERVICE` /
`TALKHERE_KEYRING_KEY`. Store one with:
```bash
secret-tool store --label="talkhere OpenAI" service talkhere key api-key
```

**Vocabulary bias** — put jargon/names in `~/.talkhere.prompt` (a Whisper `initial_prompt`)
so words like project names transcribe correctly.

**Log** — `~/.talkhere.log` records each run (trigger, backend, duration, a short preview).
No secrets are logged.

## Backends

| Backend | Latency (≈5 s clip) | Privacy | Needs |
|---|---|---|---|
| **local (GPU)** *(default)* | ~1–2 s warm, ~3.5 s cold | fully offline | NVIDIA GPU + `requirements.txt` |
| **local (CPU)** | slow (tens of seconds) | fully offline | just CPU (use a small model) |
| **api (OpenAI)** | ~1–2 s (network) | audio leaves the machine | `OPENAI_API_KEY` |

talkhere tries `local(cuda) → local(cpu) → api` and uses the first that works, logging any
downshift; pin one with `--backend`.

**NVIDIA 50-series (Blackwell) note:** these need CUDA 12.8+ / cuDNN 9 / CTranslate2 ≥ 4.5
and **`compute_type=float16`** (int8 crashes with `cuBLAS NOT_SUPPORTED`). The
`requirements.txt` pins working versions; talkhere ctypes-preloads the pip-installed
cuDNN/cuBLAS at model load, so you don't need to set `LD_LIBRARY_PATH`. Developed and tested
on an RTX 5060 Ti.

### Optional i3blocks indicator
A ready-made block that shows 🎙 while recording lives in `i3blocks/` (config snippet +
script). Point your i3blocks config at it with `signal=4`, and keep the `pkill -RTMIN+4
i3blocks` in the bindings above.

## Troubleshooting

- **Nothing gets typed** → is `xdotool` installed? Without it, talkhere falls back to the
  clipboard and notifies you — just paste. Check `~/.talkhere.log`.
- **`libcublas.so.12 not found` / `libcudnn…`** → install the GPU wheels
  (`pip install -r requirements.txt`), or use `--backend api` / `TALKHERE_DEVICE=cpu`.
- **`cuBLAS … NOT_SUPPORTED` on a 50-series GPU** → keep `compute_type=float16` (the default).
- **Nothing captured / no speech** → check your default source (`pactl list sources short`,
  `arecord -l`) and that the mic isn't muted.
- **Accents look wrong in one app** → try `--sink paste` (sets the clipboard then sends a
  paste key); set the app's chord via `[sink.paste] paste_key`.
- **Too slow** → use `large-v3-turbo` (default) or a smaller model; the local GPU path pays a
  one-time ~2 s model load per invocation.

## How it works

One small, literate Python file (`talkhere.py`): a toggle state machine backed by a runtime
lock-file (no daemon), a pluggable **backend** (`transcribe`) and **sink** (`deliver`), a
detached recorder, and best-effort feedback. The design is documented spec-first under
[`kb/`](kb/INDEX.md) (built with a spec-driven method); the knowledge base is machine-checked
by `tools/kb-lint.py` via a pre-commit hook.

## Development

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest                 # hermetic unit tests (no GPU/mic/X needed)
# GPU integration test (transcribes a speech wav):
TALKHERE_TEST_WAV=/path/to/speech.wav .venv/bin/python -m pytest -m integration -o addopts=""
tools/p3_livetest.sh                       # live accent-injection check (needs X + xdotool)
```

## Philosophy

talkhere follows the KISS principle: it does one specific thing and aims to do it right,
with minimal dependencies and clear semantics. Contributions are welcome as long as they
adhere to this philosophy!

## Credits & License

Inspired by [revisor](https://github.com/yurug/revisor). Speech recognition by
[OpenAI Whisper](https://github.com/openai/whisper) via
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) / CTranslate2.

MIT — see [LICENSE](LICENSE).
