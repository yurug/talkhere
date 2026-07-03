# talkhere — project instructions

`talkhere` is a **talk-to-type** tool for Linux: press a hotkey, speak, and the
recognised text is injected at the cursor of whatever window has focus (terminal,
emacs, browser, i3-anything). It is the spoken-input sibling of
[`revisor`](../../../perso/dev/revisor) (which revises clipboard text via an LLM):
same KISS philosophy — one script, do one thing right, clear semantics, minimal deps.

## How to work on this project

This project is built with the **Agentic Dev Kit** spec-driven method
(`~/work/dev/agentic-dev-kit`). The knowledge base is the source of truth.

- **Start here:** `kb/INDEX.md` → routing tables in `kb/indexes/by-task.md`.
- **Before implementing:** read the relevant `kb/spec/`, `kb/properties/`, and any
  `kb/external/` file for a dependency you touch. External runtime behaviour
  (GPU/CUDA quirks, xdotool key simulation) is documented there — do not guess.
- **Riskiest-first:** the Step-1 vertical slice proves the scary path (local Whisper
  on the Blackwell GPU + accent-correct injection) end to end. See `kb/plan.md`.
- **KISS is a hard constraint:** prefer stdlib + system tools (`pw-record`, `xdotool`,
  `secret-tool`, `notify-send`) over new Python dependencies. `faster-whisper` is the
  one heavy dependency and it is optional (API backend needs none).

## Target machine (verified 2026-07-03 on pangoline)

- **X11 + i3** (`XDG_SESSION_TYPE=x11`, `DESKTOP=i3`) → inject with `xdotool` (X11 only).
- **GPU:** NVIDIA RTX 5060 Ti 16 GB, **Blackwell / sm_120** (bleeding edge — see
  `kb/external/faster-whisper-blackwell.md`; the key gotcha is `compute_type=float16`,
  INT8 crashes).
- **Audio:** PipeWire (`pw-record`, `pactl`) + ALSA (`arecord`) + `ffmpeg`/`sox`.
- **Feedback:** `notify-send`/`dunst`, `paplay`, `i3blocks`.
- **Secrets:** OpenAI key in GNOME keyring (`secret-tool`), service `revisor`, key
  `api-key` (reused by the API backend). Never hard-code keys.
- pangolin (laptop) has no such GPU → it must fall back to the API or CPU backend.

## Non-negotiable conventions

1. Everything non-throwable goes on git (per `~/CLAUDE.md`).
2. No secret in the source or in git history. Fetch from keyring/env at runtime.
3. Every system change (packages, i3 binding, udev) is mirrored into `README.md`
   install steps so a fresh machine can be bootstrapped.
4. Literate style: explain the WHY; a bilingual FR/EN user reads accented output —
   accent-correctness is a first-class acceptance criterion, not an afterthought.
