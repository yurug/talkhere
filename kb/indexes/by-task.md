---
id: index-by-task
type: index
summary: "Given my task, what do I load?" — ordered reading bundles for implement / debug / test / extend.
domain: meta
last-updated: 2026-07-03
---
# By-task routing table

## Implement (a slice from plan.md)
1. `plan.md` — the step and its acceptance criteria.
2. `spec/algorithms.md` — the state machine you're realising.
3. `properties/functional.md` + `edge-cases.md` — the P/T IDs the step must satisfy.
4. The `external/` file for any dependency the step touches (backend → faster-whisper /
   openai; sink → xdotool; recorder → audio-capture).
5. `architecture/overview.md` — the interface you implement against.
6. `conventions/code-and-testing.md` — style + test-naming.
**Key questions this answers:** what am I building, what must hold, how does the dep behave.

## Debug (something misbehaves)
1. `spec/error-taxonomy.md` — match the symptom to E1–E13 and its intended handling.
2. `properties/edge-cases.md` — is this a known T-entry?
3. Relevant `external/` file — a dependency gotcha (float16, WAV header, xdotool accents).
4. `~/.talkhere.log` — the runtime trace (NF6).

## Test (add/repair tests)
1. `properties/functional.md` + `non-functional.md` + `edge-cases.md` — the catalogue.
2. `conventions/code-and-testing.md` — naming (`test_P3_…`), fakes, Xvfb integration.
3. `runbooks/audit-checklist.md` — the coverage gate.

## Extend (new backend / sink / Wayland)
1. `architecture/overview.md` — the `Backend`/`Sink` Protocols to implement.
2. The relevant ADR (0001 backend, 0003 sink) for the decision context.
3. `domain/prd.md` "Out of scope" — confirm it's wanted before building (e.g. Wayland).

## Orient (new to the project)
`INDEX.md` → this file → `domain/prd.md` → `spec/algorithms.md`. That's the whole idea in
four files.
