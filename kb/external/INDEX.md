---
id: external-index
type: index
summary: Routing table for external/ — the third-party runtime behaviours talkhere depends on.
domain: meta
last-updated: 2026-07-03
---
# External dependencies — routing table

- `faster-whisper-blackwell.md` — **highest-risk.** Version matrix, the float16-not-int8
  crash, model choice, model-load-latency tension, CPU fallback. Read before the local backend.
- `xdotool-x11-typing.md` — Unicode-safe injection flags, the accent/layout gotcha (P3),
  paste-sink chords. Read before the sinks.
- `audio-capture-pipewire.md` — pw-record/arecord command, WAV-header finalisation on stop,
  silence/duration guards. Read before the recorder.
- `openai-transcription-api.md` — the dependency-free api backend (curl + keyring key).

Rule (ADK): document ACTUAL runtime behaviour and verify it on-device before building on it.
Every claim here is tagged researched vs verified; Step 1 flips the risky ones to verified.
