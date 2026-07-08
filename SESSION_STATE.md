# SESSION_STATE — talkhere

## What talkhere is
Talk-to-type for Linux/X11+i3: hotkey → speak → recognised text injected at the cursor of
the focused window. Spoken-input sibling of revisor. KISS single Python script.

## Method
Following the Agentic Dev Kit spec-driven method (`~/work/dev/agentic-dev-kit`).
The KB under `kb/` is the source of truth. Start at `kb/INDEX.md`.

## Progress (2026-07-03)
- **Done:** Phase 0 orient · Phase 0.5 premortem (in chat) · env reconnaissance on pangoline
  · web research on Blackwell/faster-whisper · Phase 1 questions (defaults chosen) ·
  Phase 2 KB (22 files) · Phase 3 plan. `git init` done; about to make first commit.
- **Key facts:** X11+i3 → xdotool. GPU RTX 5060 Ti (Blackwell sm_120): faster-whisper needs
  CUDA 12.8/cuDNN9/CT2≥4.5 and **float16 (int8 crashes)**. Audio via pw-record. OpenAI key in
  keyring service=revisor. xdotool NOT installed yet.
- **Decisions (all revisable, config points):** local STT default + api fallback ladder;
  toggle hotkey + lockfile (no daemon); xdotool `type` sink degrading to clipboard;
  auto-detect language + override.

## Harness update (2026-07-08) — adopted the refreshed Agentic Dev Kit
- **kb-lint** vendored at `tools/kb-lint.py`; KB now passes `kb-lint kb --strict` (26 files,
  0/0). Fixed a brace-glob link, added `architecture/decisions/INDEX.md`, path-qualified
  bare links, de-orphaned the spec/properties sub-indexes.
- **pre-commit hook** `.githooks/pre-commit` (enabled via `git config core.hooksPath
  .githooks`) runs kb-lint --strict on any staged `kb/` change; verified it blocks a broken
  link and passes clean. Bypass: `git commit --no-verify`.
- **CLAUDE.md** gained the *KB routing protocol* (read INDEX first, same-commit KB rule,
  lint gate).
- **PENDING (needs user OK):** the SessionStart hook that injects `kb/INDEX.md` into context
  each session — writing `.claude/settings.json` was blocked as agent self-modification.
  Snippet to add is in `~/work/dev/agentic-dev-kit/templates/settings/kb-sessionstart.settings.json`.

## GATE — waiting on the user
1. Answer/confirm `kb/questions-round1.md` (esp. Q5 model-load-latency vs no-daemon,
   Q7 hotkey, Q8 repo location/publish).
2. Approve `kb/plan.md`.
Then: **Step 0** (install xdotool + venv + faster-whisper, verify Blackwell float16) — a
system change needing explicit go-ahead — then **Step 1** vertical slice.

## Exact next step
On approval: run Step 0 provisioning and its smoke-test; record the result (researched→
verified) in `kb/external/faster-whisper-blackwell.md`; then implement `talkhere --once`
(record → LocalBackend float16 → TypeSink), proving NF1 latency + P3 accents.

## The one open risk to resolve first
Model-load latency (seconds) vs zero-idle no-daemon (NF2/ADR0002) vs ≤2 s latency (NF1).
Step 1 measures and picks: fast model / optional warm helper / api-default. See plan.md ⚠.
