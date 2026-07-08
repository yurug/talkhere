# SESSION_STATE — talkhere

## What talkhere is
Talk-to-type for Linux/X11+i3: hotkey → speak → recognised text injected at the cursor of
the focused window. Spoken-input sibling of revisor. KISS single Python script.
Built with the Agentic Dev Kit spec-driven method; KB under `kb/` is the source of truth
(start at `kb/INDEX.md`). KB is machine-checked (`tools/kb-lint.py`, pre-commit hook).

## Progress
- **Phases 0–3 (2026-07-03):** premortem, env recon, Blackwell research, KB (26 files), plan.
- **Harness (2026-07-08):** adopted refreshed ADK — kb-lint + `.githooks/pre-commit`
  (`core.hooksPath .githooks`) + CLAUDE.md routing protocol. KB passes `--strict` (0/0).
- **Step 0 DONE (2026-07-08):** `.venv` with faster-whisper 1.2.1 / ctranslate2 4.8.1 /
  nvidia-cudnn-cu12 9.24 / nvidia-cublas-cu12 12.9. **Blackwell float16 VERIFIED** — jfk.wav
  → exact transcript. Recorder (pw-record + SIGINT) verified. Runtime facts recorded in
  `kb/external/faster-whisper-blackwell.md` (cuBLAS separate pkg; ctypes-preload instead of
  LD_LIBRARY_PATH). Q5 measured: per-invocation ~3.5s, warm ~1.3s → default per-invocation.
- **Step 1 mostly DONE (2026-07-08):** `talkhere.py` — `--once`, Local+Api backends, Type/
  Paste/Clipboard sinks, feedback, logging, config. 13 unit tests + 1 GPU integration test
  pass. Live: record→GPU→clipboard delivers exact text; P5 empty-guard works.

## GATE / pending on the user
1. **`sudo apt-get install -y xdotool`** (needs your password; run `! sudo apt-get install -y
   xdotool`). Unblocks the `type` sink + the live P3 accent test (last Step-1 item).
2. **SessionStart hook** still not installed — writing `.claude/settings.json` is blocked as
   agent self-modification. Snippet in `~/work/dev/agentic-dev-kit/templates/settings/
   kb-sessionstart.settings.json`; paste it or run me outside auto mode.
3. Open questions in `kb/questions-round1.md` beyond Q5 (answered): Q7 hotkey, Q8 repo
   location/publish, etc. — defaults stand until you say otherwise.

## Exact next step
- When xdotool is in: run the live P3 accent round-trip ("Café — déçu, ça va ? 🙂" into a
  scratch xterm, assert byte-equality) → close Step 1.
- Then **Step 2 — toggle UX**: state machine + `recording.json` + flock, detached recorder
  START/STOP, `--stop`/`--cancel`, cues, i3 binding + `~/.local/bin/talkhere` symlink,
  i3blocks `--status` indicator. (Recorder detach/SIGINT already proven.)

## Notes
- Home-dir rule: xdotool is a system change → mirror into dotfiles `bootstrap.sh` + MACHINE.md
  once installed. venv deps are project-local (requirements.txt).
- talkhere currently lives in `work/dev/` — confirm work vs perso (Q8) before publishing.
