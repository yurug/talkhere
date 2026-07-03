---
id: glossary
type: glossary
summary: Canonical vocabulary for talkhere; every other KB file draws its terms from here.
domain: meta
last-updated: 2026-07-03
---
# Glossary — canonical terms for talkhere

Controlled vocabulary. Use these exact names in code, commits, and other KB files.

## Core concepts

- **talk-to-type** — the product: hotkey → speak → recognised text injected at the
  cursor of the focused window. Contrast **revisor** (clipboard text → LLM → clipboard).
- **utterance** — one recording session: from *start* to *stop*, one audio clip, one
  transcription, one injection.
- **backend** (STT backend) — a pluggable transcription engine implementing the
  `transcribe(wav_path, lang) -> text` contract. Concrete backends: **local** backend
  (faster-whisper on GPU) and **api** backend (OpenAI transcription).
- **sink** (delivery sink) — a pluggable way to deliver text to the user. Concrete
  sinks: **type** (xdotool key simulation), **paste** (clipboard + paste keystroke),
  **clipboard** (clipboard only, revisor-style).
- **trigger** — how an utterance is started/stopped. talkhere uses **toggle**: one
  hotkey; first press starts, second press stops.
- **state file / lock file** — a file under the runtime dir that records whether a
  recording is in progress (and the recorder PID). Absence = idle. See `spec/algorithms.md`.

## Environment terms

- **injection** — placing text into the focused application by simulating input
  (`xdotool type`) or a paste keystroke. NOT the same as setting the clipboard.
- **compute_type** — CTranslate2/faster-whisper numeric precision. On Blackwell
  (sm_120) must be **float16**; **int8** crashes (`cuBLAS NOT_SUPPORTED`).
- **primary / clipboard** — the two X11 selections (middle-click paste vs Ctrl+C/V).
- **runtime dir** — `${XDG_RUNTIME_DIR:-/tmp}/talkhere` — holds the state file, the
  in-progress wav, and the recorder PID. Throwable.

## Config / files

- **config file** — `~/.config/talkhere/config.toml` (optional). Overrides defaults.
- **prompt / vocabulary file** — `~/.talkhere.prompt` (optional): a Whisper
  `initial_prompt` to bias spelling of names/jargon (mirrors revisor's `~/.revisor`).
- **log file** — `~/.talkhere.log`. Timestamped, append-only (mirrors revisor).

## Related files
- `domain/prd.md` — what talkhere does with these terms.
- `spec/algorithms.md` — the toggle state machine that uses the state/lock file.
