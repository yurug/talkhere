# Phase-5 quality audit — talkhere (2026-07-08)

Scope: `talkhere.py` + `test_talkhere.py` after Steps 0–3. Result: **0 criticals, 0 highs.**
One medium (file size) reconciled by decision. All checks below verified this session.

## 1. Test-gap
- 25 unit tests + 1 GPU integration test pass. Property-named coverage: P1, P3, P4, P5, P6,
  P7, P8, P9, P10, P11, E6, E9, T9 — plus config round-trip, api key sourcing, paste sink.
- P2 (inject-to-focus) covered by the live P3 test (`tools/p3_livetest.sh`) + TypeSink unit.
- NF1 latency measured (2.2 s load + ~1.3 s/5 s clip). NF6 no-leak asserted by test.
- **Gap accepted:** no automated coverage % (pytest-cov not installed); the property-named
  suite is the coverage contract instead. Low risk for a ~550-code-line single file.

## 2. Security — CLEAN
- No `sk-`/`Bearer` literal anywhere in git history (only the benign keyring attribute
  name `"api-key"`). Key fetched at runtime from env/keyring.
- API key passed to curl via **stdin config (`-K -`)**, not argv → not visible in `ps`.
- Transcribed text never interpolated into a shell string: TypeSink uses `xdotool … --file -`
  with the text on stdin; no `shell=True`/`os.system` anywhere (all argv lists).
- `~/.talkhere.log` contains 0 secret-ish lines; only a 40-char transcript preview (NF6).
- State/wav under `$XDG_RUNTIME_DIR/talkhere` (per-user), not a shared /tmp path.

## 3. Performance
- NF1 met on GPU (per-invocation ~3.5 s, warm ~1.3 s). Generator fully consumed before timing.
- CPU fallback works but slow (~24 s/11 s clip with `base`) → on GPU-less hosts prefer the
  API backend (~2.3 s). Recorded in NF5 note.

## 4. UX
- Audio cue + notify-send on start/stop/done; every error path notifies with an actionable
  message (E1–E13). `--help` documents the inverted `--status` exit code.

## 5. Spec compliance
- All `cli-and-config.md` flags implemented (`--once/--stop/--cancel/--status/--lang/
  --backend/--sink/-v/--help`). Fallback ladder (local→cpu→api, sink→clipboard) matches
  `error-taxonomy.md`. Both fallbacks exercised live.

## 6. Simplicity — MEDIUM (reconciled)
- `talkhere.py` is ~700 lines, over the KB's original "~400 → split" heuristic. Composition:
  ~40% docstrings/comments (ADK literate style), ~550 non-blank. **Decision:** keep one file
  (KISS / revisor-parity / project CLAUDE.md "one script"); `arch/overview.md` updated to a
  logic-based threshold. No package split.

## 7. Provability
- Behaviours annotated with the property they enforce (`P3`, `P5`, `E6`, …). Stale-state
  recovery (E9/T4) reasoned + tested; no path leaves a stuck lock (flock always released in
  `finally`; stale pid self-heals).

## Follow-ups (non-blocking)
- Optional `--serve` warm-model helper for sub-2 s latency (documented, deferred).
- pangolin (laptop, no GPU) portability is by-config (api/cpu) — verify on that host later.
