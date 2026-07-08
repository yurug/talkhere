# SESSION_STATE — talkhere

## What talkhere is
Talk-to-type for Linux/X11+i3: press `$mod+t`, speak, press again → recognised text is typed
at the cursor of the focused window. `$mod+Shift+t` cancels. Spoken-input sibling of revisor.
KISS single Python script; local faster-whisper on the GPU by default, CPU/API fallbacks.
Built with the Agentic Dev Kit method; KB under `kb/` is the source of truth (`kb/INDEX.md`),
machine-checked by `tools/kb-lint.py` + `.githooks/pre-commit`.

## Status — ALL PLAN STEPS DONE (2026-07-08)
- **Harness:** kb-lint + pre-commit + CLAUDE.md routing protocol. KB 27 files, 0/0.
- **Step 0:** `.venv` (faster-whisper 1.2.1 / ct2 4.8.1 / cudnn 9.24 / cublas 12.9). Blackwell
  float16 VERIFIED. In-process ctypes preload of cuDNN/cuBLAS (no LD_LIBRARY_PATH needed).
- **Step 1:** record→transcribe→deliver; Local/Api backends; Type/Paste/Clipboard sinks.
  P3 accents VERIFIED live (`tools/p3_livetest.sh`).
- **Step 2:** toggle state machine (recording.json + flock, detached START/STOP, stale
  recovery); i3 `$mod+t`/`$mod+Shift+t`; i3blocks 🎙 indicator (RTMIN+4).
- **Step 3:** fallback ladder (API 2.3 s + CPU live); config.toml round-trip; prompt bias;
  api key off argv (curl `-K -`). Phase-5 audit 0 criticals
  (`kb/reports/audit-2026-07-08-phase5.md`).
- **Tests:** 25 unit + 1 GPU integration, all green.

## How to use
`$mod+t` to dictate anywhere; `$mod+Shift+t` cancels. `talkhere --once N` / `--backend api`
/ `--sink clipboard` / `--lang fr` for scripting. Log: `~/.talkhere.log`.

## Publishable (done 2026-07-08)
LICENSE (MIT); rewritten general README (full manual); `i3blocks/` (block script +
config.example); `.github/workflows/ci.yml` (hermetic pytest + kb-lint --no-git, verified
green in a clean venv). Personal dependency removed — api key sourcing is configurable
(`TALKHERE_KEYRING_SERVICE`/`_KEY`, default talkhere/api-key) instead of hard-coded revisor.

## Open (non-blocking)
- **dotfiles: talkhere parts COMMITTED** (`dedea94` in `~/perso/dev/dotfiles`: i3/config,
  i3blocks/config, i3blocks/scripts/talkhere, xdotool in bootstrap.sh). Your other WIP
  (Android/emacs/git/backup/shell + the MACHINE.md talkhere row, which shares a hunk with
  your Android edits) left untouched for you.
- **yann's API fallback:** keyring service default is now `talkhere`. Local GPU is the
  default so this rarely matters; to reuse your revisor key: `export
  TALKHERE_KEYRING_SERVICE=revisor` (or store a `talkhere` keyring entry).
- **SessionStart hook** uninstalled (blocked as self-mod).
- **Q8:** publish under `yurug/talkhere` (sibling of yurug/revisor)? work vs perso? Undecided.
- Optional `--serve` warm helper (~1.3 s latency); pangolin (laptop) portability check.

## Next if resumed
Nothing required — complete, working, and publishable. Optional: publish (Q8), `--serve`,
laptop check.
