---
id: runbook-audit-checklist
type: procedure
summary: Multi-axis quality gate to run (Ralph Loop) before declaring a slice done.
domain: quality
last-updated: 2026-07-08
related: [properties-functional, properties-non-functional, spec-error-taxonomy]
---
# Audit checklist (Phase 5 gate)

Run each axis as an independent pass; fix all criticals/highs; re-audit until 0 criticals.

## 1. Test-gap
- [ ] Every P1–P11 has ≥1 test named after it. Every T1–T10 has a test.
- [ ] P3 (accents) and P5 (never inject empty) have dedicated regressions that run always.
- [ ] Coverage of `talkhere.py` reported; uncovered branches justified.

## 2. Security
- [ ] No API key in source, log, or git history (`git log -p | grep -i key`).
- [ ] Transcribed text is never interpolated into a shell command (injection via `--file -`,
      not string-built commands).
- [ ] Log preview truncated; no full transcript or key leaked (NF6).
- [ ] `recording.json` / wav under a per-user runtime dir, not world-readable /tmp path reuse.

## 3. Performance
- [ ] NF1 measured on pangoline: stop→text ≤ 2 s for ~5 s clip. Record the number.
- [ ] Model-load strategy chosen and justified (per-invocation vs warm helper) — see the
      open risk in `external/faster-whisper-blackwell.md` Agent notes.
- [ ] `transcribe` generator fully consumed before timing.

## 4. UX
- [ ] Start/stop/done cues are unmistakable (sound + notification).
- [ ] Every error path yields a human message naming the fix (E1–E13), never a bare trace.
- [ ] `--help` documents flags incl. the inverted `--status` exit code.

## 5. Spec compliance
- [ ] Each `spec/` claim maps to code. Flags in `spec/cli-and-config.md` all implemented or
      explicitly deferred.
- [ ] Fallback ladder (backend + sink) behaves as `spec/error-taxonomy.md` specifies.

## 6. Simplicity
- [ ] Still one file, no gratuitous dependency. Anything added earns its place vs KISS.
- [ ] No dead flags/config keys. Could any layer be removed without losing a property?

## 7. Provability
- [ ] For each behaviour, name the property (P/NF/T) that says why it's correct.
- [ ] Stale-state recovery (E9/T4) reasoned through: no path leaves a stuck lock.

## Portability sign-off
- [ ] Runs on pangolin (no GPU) via cpu/api by config only (NF5). Documented in README.
