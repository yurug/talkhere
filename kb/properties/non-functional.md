---
id: properties-non-functional
type: constraint
summary: Measurable non-functional criteria NF1–NF6 (latency, footprint, deps, privacy).
domain: quality
last-updated: 2026-07-03
related: [properties-functional, external-faster-whisper-blackwell]
---
# Non-functional properties

### NF1 — Stop→text latency
Local GPU backend, ~5 s utterance, `large-v3-turbo`, float16: stop→injection **≤ 2 s**
(target ≤ 1 s). Measured from STOP invocation to `sink.deliver` return.
*Check:* time a fixed sample wav through the backend on pangoline.

### NF2 — Zero idle footprint
When not recording, no talkhere process, thread, or daemon exists. A recording is exactly
one detached `pw-record`/`arecord` process + one small state file.
*Check:* `pgrep -f talkhere` empty when idle; exactly one recorder when recording.

### NF3 — Minimal dependencies
Runtime = Python stdlib + system tools (`pw-record`/`arecord`, `xdotool`, `secret-tool`,
`notify-send`, `paplay`). `faster-whisper` is the only pip dependency and is required
**only** for the local backend. The api backend needs none beyond `curl`/stdlib.
*Check:* api backend runs in a venv without faster-whisper installed.

### NF4 — Privacy default
The default (`local`) keeps audio on the machine — nothing leaves. Choosing `api` sends
audio to OpenAI; that trade-off is explicit (flag/config), never silent.
*Check:* local run makes no network call (strace/tcpdump spot check).

### NF5 — Portability across the two machines
Same script runs on pangoline (cuda) and pangolin (no GPU): device auto-falls-back to cpu,
or backend to api, without code change — config/env only.
*Check:* `TALKHERE_DEVICE=cpu` and `TALKHERE_BACKEND=api` both work on either host.

### NF6 — Observability
Every run appends a timestamped line to `~/.talkhere.log` covering: trigger branch,
backend+device used, audio duration, transcript length, sink, and any fallback taken.
No secrets or full transcripts beyond a truncated preview in the log.
*Check:* one utterance produces a parseable log line; grep shows no API key.

## Related files
- `external/faster-whisper-blackwell.md` — model/precision choices behind NF1.
- `properties/functional.md` — P10 resilience underpins NF5.
