---
id: arch-decisions-index
type: index
summary: Routing table for the Architecture Decision Records — the three choices that fork talkhere's design.
domain: meta
last-updated: 2026-07-08
---
# Architecture decisions — routing table

Each ADR: Context → Decision → Consequences → What this means for implementers.

- `0001-pluggable-stt-local-default.md` — **STT is a pluggable `Backend`**; default local
  faster-whisper on GPU (float16 on sm_120) with a `local(cuda)→local(cpu)→api` fallback
  ladder. Read when touching transcription.
- `0002-toggle-trigger-lockfile.md` — **toggle hotkey + runtime lock-file, no daemon**;
  presence of `recording.json` is the record/idle state. Read when touching the trigger,
  recorder lifecycle, or concurrency (P8).
- `0003-text-delivery-xdotool-type.md` — **delivery is a pluggable `Sink`**; default `type`
  via xdotool (Unicode-safe), degrading to clipboard; `paste`/`clipboard` selectable. Read
  when touching injection or the accent path (P3).

## Related files
- `../overview.md` — the module structure these decisions shape.
