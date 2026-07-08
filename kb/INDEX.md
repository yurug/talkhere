---
id: kb-index
type: index
summary: Root routing table for the talkhere knowledge base — start here.
domain: meta
last-updated: 2026-07-08
---
# talkhere — Knowledge Base

**talkhere** is a talk-to-type tool for Linux/X11+i3: one hotkey → speak → the recognised
text is injected at the cursor of the focused window. It is the spoken-input sibling of
`revisor`, same KISS philosophy (one script, done right). Default STT is local
faster-whisper on the GPU; delivery is xdotool typing; control is a single toggle hotkey.

## How to use this KB
Agent navigation: rank files by title/summary, open few, follow "Related files". Start with
`indexes/by-task.md` — it maps your task (implement / debug / test / extend) to an ordered
reading bundle.

## Quick-load bundles
| Goal | Read in order |
|------|---------------|
| Understand the idea | `domain/prd.md` → `spec/algorithms.md` |
| Implement a slice | `plan.md` → `spec/algorithms.md` → `properties/functional.md` + `properties/edge-cases.md` → relevant `external/*` → `architecture/overview.md` |
| Understand the risky dep | `external/faster-whisper-blackwell.md` (+ `external/INDEX.md`) |
| Why is it built this way | `architecture/overview.md` → `architecture/decisions/000{1,2,3}-*.md` |
| Debug a failure | `spec/error-taxonomy.md` → `properties/edge-cases.md` → `~/.talkhere.log` |
| Judge "is it done" | `runbooks/audit-checklist.md` |

## Map
- `GLOSSARY.md` — canonical terms.
- `domain/prd.md` — product requirements, user stories, out-of-scope.
- `spec/INDEX.md` → `spec/algorithms.md` (toggle state machine), `spec/cli-and-config.md`, `spec/error-taxonomy.md`.
- `properties/INDEX.md` → `properties/functional.md` (P1–P11), `properties/non-functional.md` (NF1–NF6), `properties/edge-cases.md` (T1–T10).
- `architecture/overview.md` + `architecture/decisions/INDEX.md` (3 ADRs: STT / trigger / delivery).
- `external/INDEX.md` → faster-whisper-blackwell, xdotool-x11-typing, audio-capture-pipewire, openai-transcription-api.
- `conventions/code-and-testing.md`, `runbooks/audit-checklist.md`, `indexes/by-task.md`.
- `plan.md` — the risk-ordered implementation plan.
- `questions-round1.md` — decisions taken + open questions for the user.
- `reports/` — premortem/audit/quiz artifacts (added as generated).

## Status
Phases 0–3 of the ADK method complete: env researched, KB written, plan drafted. The KB is
mechanically validated — `tools/kb-lint.py kb --strict`, wired into `.githooks/pre-commit`.
**Gate:** awaiting user answers in `questions-round1.md` and approval of `plan.md` before
Step 0 provisioning + Phase 4 implementation. File count: 26 KB files.
