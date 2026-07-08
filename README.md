# talkhere

Talk-to-type for Linux/X11: press a hotkey, speak, and the recognised text is injected at
the cursor of whatever window has focus (terminal, emacs, browser, i3-anything). The
spoken-input sibling of [revisor](../../../perso/dev/revisor) — same KISS spirit: one
script, done right. Transcription runs **locally** on the GPU by default (private, offline,
no per-use cost), with an OpenAI-API fallback.

> Status: **Step 1 complete** (the record → transcribe → deliver slice; `--once` mode).
> The single-hotkey toggle UX is Step 2 (`kb/plan.md`). Built with the spec-driven method
> in `kb/` — start at `kb/INDEX.md`.

## Install

### 1. System tools
```bash
sudo apt-get install -y xdotool            # inject text into the focused X11 window
# already present on a typical Debian 13 desktop: pipewire (pw-record), xclip,
# libnotify-bin (notify-send), pulseaudio-utils (paplay). arecord is an audio fallback.
```

### 2. Python venv + backend
```bash
cd talkhere
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # local GPU backend (faster-whisper + cuDNN/cuBLAS)
```
The local backend needs an NVIDIA GPU with a recent driver (verified: RTX 5060 Ti /
Blackwell, driver 580, float16). No CUDA toolkit is required — the pip wheels carry the
runtime, and talkhere ctypes-preloads cuDNN/cuBLAS itself (details:
`kb/external/faster-whisper-blackwell.md`). First run downloads the model (~1.6 GB) to the
Hugging Face cache.

**No GPU?** Use the API backend (`--backend api`) or CPU (`TALKHERE_DEVICE=cpu`). The API
backend needs only `curl` + an OpenAI key: `OPENAI_API_KEY`, else the GNOME keyring entry
`service=revisor key=api-key` (shared with revisor).

## Usage (Step 1)

```bash
.venv/bin/python talkhere.py --once 4          # record 4s, transcribe, type at the cursor
.venv/bin/python talkhere.py --once 4 --sink clipboard   # put it on the clipboard instead
.venv/bin/python talkhere.py --once 4 --lang fr          # force French
.venv/bin/python talkhere.py --once 4 --backend api      # transcribe via OpenAI
.venv/bin/python talkhere.py --status                    # idle|recording (exit 0|1)
```

Optional `~/.talkhere.prompt` biases Whisper's spelling of names/jargon; optional
`~/.config/talkhere/config.toml` sets defaults (see `kb/spec/cli-and-config.md`). Runtime
log: `~/.talkhere.log`.

## Develop

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest                      # hermetic unit tests (no GPU/mic/X)
TALKHERE_TEST_WAV=/path/to/speech.wav .venv/bin/python -m pytest -m integration -o addopts=""
```
KB invariants are machine-checked: `tools/kb-lint.py kb --strict` (wired into
`.githooks/pre-commit` via `git config core.hooksPath .githooks`).

## License
MIT (matching revisor).
