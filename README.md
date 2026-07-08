# talkhere

Talk-to-type for Linux/X11: press a hotkey, speak, and the recognised text is injected at
the cursor of whatever window has focus (terminal, emacs, browser, i3-anything). The
spoken-input sibling of [revisor](../../../perso/dev/revisor) — same KISS spirit: one
script, done right. Transcription runs **locally** on the GPU by default (private, offline,
no per-use cost), with an OpenAI-API fallback.

> Status: **working** — all three plan steps complete (record → transcribe → deliver via a
> single toggle hotkey; local GPU Whisper with CPU/API fallbacks; accents verified). Built
> with the spec-driven method in `kb/` — start at `kb/INDEX.md`.

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

### 3. Hotkey (the way you actually use it)
Symlink the launcher onto your PATH and bind it in i3:
```bash
ln -s "$PWD/bin/talkhere" ~/.local/bin/talkhere      # runs talkhere from its venv
```
```
# ~/.config/i3/config
bindsym $mod+t exec --no-startup-id "$HOME/.local/bin/talkhere; pkill -RTMIN+4 i3blocks"
bindsym $mod+Shift+t exec --no-startup-id "$HOME/.local/bin/talkhere --cancel; pkill -RTMIN+4 i3blocks"
```
Optional i3blocks mic indicator: a `talkhere` block (`signal=4`) that shows 🎙 while
recording — see this repo's dotfiles for the block script.

## Usage

**Toggle (normal use):** press **`$mod+t`** — a cue confirms recording started; speak; press
**`$mod+t`** again — the text is typed at your cursor. **`$mod+Shift+t`** cancels.

```bash
# scripting / one-shot forms:
talkhere --once 4                # record 4s, transcribe, type at the cursor
talkhere --once 4 --sink clipboard   # put it on the clipboard instead
talkhere --lang fr               # force French for this utterance
talkhere --backend api           # transcribe via OpenAI instead of the local GPU
talkhere --stop                  # force-stop an in-progress recording
talkhere --status                # idle|recording (exit 0|1) — for i3blocks
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
