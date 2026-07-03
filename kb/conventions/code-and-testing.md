---
id: conventions-code-and-testing
type: procedure
summary: Code style, error-handling, and testing conventions for talkhere — KISS, literate, property-referenced tests.
domain: conventions
last-updated: 2026-07-03
related: [properties-functional, arch-overview]
---
# Conventions — code, errors, tests

## Code style (KISS, revisor-lineage)
- **One file** `talkhere.py`, Python 3.11+ (target 3.13 on pangoline), stdlib-first.
- Small functions (< 30 lines), clear names from `GLOSSARY.md`. No `Any`-typing sloppiness;
  use `Protocol` for `Backend`/`Sink`. Type-hint public functions.
- **Literate**: file header (purpose, spec refs, key decisions); every public function has a
  docstring (@param meaning / @returns / @raises / `@invariant P<N>`); every non-obvious
  conditional carries a WHY comment; every magic number is named/explained. Comment the
  WHY, never restate code. Target ≥30% comment density but never pad.
- Lazy-import heavy/optional deps (`faster_whisper`) inside the class that needs them.
- No secret in source; fetch from env/keyring at runtime (mirror revisor's `_keyring`).

## Error handling
- Hotkey-invoked ⇒ no visible terminal ⇒ **the notification is the UI**. Every user-
  affecting failure: append to `~/.talkhere.log` AND `notify-send`. See `spec/error-taxonomy.md`.
- Feedback/cue helpers are best-effort: they must never raise into the pipeline.
- Prefer a safe no-op (nothing captured) or the clipboard fallback over injecting uncertain
  text (P5/P7). Never let a Python traceback be the only signal (P9).
- Wrap the whole `main` in try/except that logs, notifies, releases the lock, and exits
  non-zero — a crash must still clean the flock and stale state.

## Testing (pytest)
- **Every test name starts with its property/edge ID**: `def test_P3_type_sink_accents()`,
  `def test_T3_wav_header_finalised()`. Coverage is then greppable against the KB.
- **DI + fakes**: `FakeBackend` (returns a scripted string / ""), `FakeSink` (records
  delivered text), `FakeRecorder`. The orchestrator/state machine is unit-tested with these
  — no audio or GPU needed for the bulk of the suite.
- **Integration tests** (marked, opt-in): `TypeSink` round-trip into a scratch X client under
  Xvfb for P3; recorder start/stop for T3; live local backend on a fixture wav for NF1.
- **Edge matrix**: one test per T-entry in `properties/edge-cases.md`.
- **Property/fuzz**: feed the postprocessor random Unicode; assert interior fidelity (P6).
- Run: type-check (`ruff`/`mypy` if adopted), `pytest`, on every change. Red-baseline first
  (commit failing tests that pin the gap), then green.

## Related files
- `properties/functional.md` — the P-IDs tests must reference.
- `runbooks/audit-checklist.md` — the quality gates before "done".
