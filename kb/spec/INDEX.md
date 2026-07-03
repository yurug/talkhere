---
id: spec-index
type: index
summary: Routing table for the spec/ folder.
domain: meta
last-updated: 2026-07-03
---
# Spec — routing table

- `algorithms.md` — the toggle state machine + record→transcribe→inject pipeline + lock protocol. **Read first.**
- `cli-and-config.md` — flags, exit codes, env vars, config.toml, on-disk files.
- `error-taxonomy.md` — every failure E1…E13, its user signal and exit code; the fallback ladder.

Data model is deliberately thin (one transient `recording.json` record, defined in
`algorithms.md`) so it has no separate file. Formats live in `cli-and-config.md`.
