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

## KB routing protocol (every task, every session — not just skill runs)

1. **Before ANY task — even a one-line fix** — read `kb/INDEX.md` and load the
   quick-load bundle for your task type from `kb/indexes/by-task.md`. A change made
   without the KB is how a property (P3 accents, P5 never-inject-empty) gets silently
   violated.
2. **Same-commit rule:** if a change alters behaviour a KB file describes, update that
   file (and its `last-updated`) in the SAME commit as the code. A KB updated "later"
   drifts; a drifted KB stops being trusted, then stops being maintained.
3. **Code vs KB conflict:** stop and reconcile before building on either — the KB wins
   (it is the spec) unless it is stale, in which case fix the KB in the same commit.
4. **Mechanical gate:** `tools/kb-lint.py kb --strict` must pass before any KB commit.
   It is wired into `.githooks/pre-commit` (`git config core.hooksPath .githooks`), so
   lint errors are build failures, not suggestions. Keep illustrative paths in KB prose
   inside code fences so the linter doesn't chase them.

## Target machine (verified 2026-07-03 on pangoline)

- **X11 + i3** (`XDG_SESSION_TYPE=x11`, `DESKTOP=i3`) → inject with `xdotool` (X11 only).
- **GPU:** NVIDIA RTX 5060 Ti 16 GB, **Blackwell / sm_120** (bleeding edge — see
  `kb/external/faster-whisper-blackwell.md`; the key gotcha is `compute_type=float16`,
  INT8 crashes).
- **Audio:** PipeWire (`pw-record`, `pactl`) + ALSA (`arecord`) + `ffmpeg`/`sox`.
- **Feedback:** `notify-send`/`dunst`, `paplay`, `i3blocks`.
- **Secrets:** OpenAI key (API backend) from `OPENAI_API_KEY` or GNOME keyring; the keyring
  service/key are configurable (`TALKHERE_KEYRING_SERVICE`/`_KEY`, default `talkhere`/
  `api-key`). To reuse the existing revisor key here: `export TALKHERE_KEYRING_SERVICE=revisor`.
  Never hard-code keys.
- pangolin (laptop) has no such GPU → it must fall back to the API or CPU backend.

## Non-negotiable conventions

1. Everything non-throwable goes on git (per `~/CLAUDE.md`).
2. No secret in the source or in git history. Fetch from keyring/env at runtime.
3. Every system change (packages, i3 binding, udev) is mirrored into `README.md`
   install steps so a fresh machine can be bootstrapped.
4. Literate style: explain the WHY; a bilingual FR/EN user reads accented output —
   accent-correctness is a first-class acceptance criterion, not an afterthought.
