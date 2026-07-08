# SESSION_STATE — talkhere

## What talkhere is
Talk-to-type for Linux/X11+i3: hotkey → speak → recognised text injected at the cursor of
the focused window. Spoken-input sibling of revisor. KISS single Python script.
Built with the Agentic Dev Kit spec-driven method; KB under `kb/` is the source of truth
(start `kb/INDEX.md`). KB machine-checked (`tools/kb-lint.py`, pre-commit hook).

## Progress
- **Phases 0–3 (07-03):** premortem, env recon, Blackwell research, KB (26 files), plan.
- **Harness (07-08):** kb-lint + `.githooks/pre-commit` + CLAUDE.md routing protocol. 0/0.
- **Step 0 DONE:** `.venv` (faster-whisper 1.2.1 / ctranslate2 4.8.1 / cudnn 9.24 / cublas
  12.9). Blackwell float16 VERIFIED. Q5 measured → per-invocation load (no daemon).
- **Step 1 DONE:** `talkhere.py --once` record→GPU-transcribe→deliver; Local+Api backends,
  Type/Paste/Clipboard sinks; P3 accents VERIFIED live (`tools/p3_livetest.sh`).
- **Step 2 DONE:** toggle state machine (recording.json + flock, detached START/STOP, stale
  recovery), `--stop/--cancel/--status`. Desktop wired: `~/.local/bin/talkhere` wrapper, i3
  `$mod+t` toggle + `$mod+Shift+t` cancel, i3blocks 🎙 indicator (RTMIN+4). Verified live via
  simulated keypress. **17 unit tests + 1 GPU integration test green.**

## Working now
`$mod+t` to dictate anywhere (press, speak, press → text typed at cursor). `$mod+Shift+t`
cancels. Local GPU Whisper by default; `--backend api` / `TALKHERE_DEVICE=cpu` fallbacks.

## Open / pending
- **dotfiles repo (`~/perso/dev/dotfiles`)** has the USER's pre-existing WIP; I edited
  i3/config, i3blocks/config, i3blocks/scripts/talkhere, and (pending) bootstrap.sh +
  MACHINE.md to add xdotool + talkhere — but **did NOT commit** (don't sweep up their WIP).
  User should review+commit the dotfiles repo.
- **SessionStart hook** still not installed (blocked as self-mod). Snippet in ADK
  templates/settings/kb-sessionstart.settings.json.
- **Q7 answered** ($mod+t). Q8 (talkhere in work/dev vs perso; publish?) still open.

## Next — Step 3 (resilience/config/polish + Phase-5 audit)
- Full fallback ladder cuda→cpu→api exercised; config.toml round-trip; ~/.talkhere.prompt
  vocab bias (T9); paste-sink per-app key. pangolin (no GPU) portability check (NF5).
- Run `kb/runbooks/audit-checklist.md` (0 criticals). Then Phase 6/7 (KB sync, docs).
