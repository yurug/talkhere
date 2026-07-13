---
id: properties-index
type: index
summary: Routing table for properties/ — the invariants and edge cases that define "correct".
domain: meta
last-updated: 2026-07-13
---
# Properties — routing table

- `functional.md` — P1–P12 invariants. **P3 (accent fidelity)**, **P5 (never inject on
  empty)** and **P12 (text lands in the window dictation started in, entirely)** are the
  trust-critical ones; **P8** (race), **P10** (backend fallback).
- `non-functional.md` — NF1–NF6: latency, zero idle footprint, minimal deps, privacy,
  portability, observability.
- `edge-cases.md` — T1–T10 boundary inputs → the concrete test matrix.

Implementation rule: every test name begins with the property/edge ID it defends
(`P3: …`, `T7: …`) so coverage is greppable.
