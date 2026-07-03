---
id: properties-functional
type: constraint
summary: Functional invariants P1–P11 talkhere must uphold, each with a violation example, the WHY, and a test strategy.
domain: correctness
last-updated: 2026-07-03
depends-on: [spec-algorithms, spec-error-taxonomy]
related: [properties-edge-cases, properties-non-functional]
---
# Functional properties (invariants)

Each: statement · violation example · WHY · test strategy. Test names start with the ID.

### P1 — Toggle correctness
Given IDLE, a no-arg run starts recording and leaves the state file present; given
RECORDING, a no-arg run stops and leaves the state file absent.
*Violation:* two runs both start; state file leaks after stop.
*WHY:* the whole UX is "one key, alternating"; a stuck state breaks every later press.
*Test:* drive `main()` twice against a fake recorder/backend; assert state file toggles.

### P2 — Injection lands in the focused window
On STOP, recognised text is delivered via the configured sink to the focused X11 client.
*Violation:* text printed only to stdout; clipboard set but never pasted in `type` mode.
*WHY:* "talk-to-type" means it appears where I'm typing, hands-free.
*Test:* integration test typing into a scratch X client (`xterm`/xdotool getwindowname) in CI-xvfb.

### P3 — Accent fidelity (bilingual)
Injected text preserves non-ASCII exactly: `é è à ç ù ô …` and `—`, quotes, emoji.
*Violation:* `café` typed as `cafe`; `à` dropped; wrong under a QWERTY-active layout.
*WHY:* the user dictates French constantly; a lossy path is worse than useless.
*Test:* `type` sink round-trips a fixed accented string into a scratch window; assert equality.

### P4 — Language control
`--lang fr|en` forces that language; `auto` lets the backend detect. The chosen language
reaches the backend unchanged.
*Violation:* `--lang fr` ignored; English model forced on French audio.
*Test:* assert the value threaded from flag/env/config into `backend.transcribe`.

### P5 — Never inject on empty
If the wav is too short/silent or the transcription is empty, talkhere injects nothing
and signals "nothing captured / no speech".
*Violation:* an empty string or whitespace typed into the terminal, or a stray keystroke.
*WHY:* an accidental hotkey must be a harmless no-op, not corruption of the focused buffer.
*Test:* feed silence + empty-string backend; assert sink never called, exit 0.

### P6 — Transcription fidelity (no editing)
talkhere delivers the transcript as produced (modulo whitespace trim + optional single
trailing space). It does not paraphrase, translate, or "improve" text.
*Violation:* auto-capitalising, dropping filler, LLM rewriting (that is revisor's job).
*Test:* backend returns a known string with interior spacing; assert interior bytes unchanged.

### P7 — Sink degradation preserves text
If the chosen sink's tool is missing, talkhere falls back to `clipboard` (text recoverable)
and notifies — it never drops recognised text on the floor.
*Violation:* `xdotool` missing → text silently lost.
*Test:* force `type` with xdotool absent; assert clipboard set + notification.

### P8 — Single-recorder / race safety
Concurrent no-arg invocations never spawn two recorders; the second observes the state and
becomes a STOP. Stale state (dead pid) is recovered, not fatal.
*Violation:* double keypress spawns two `pw-record` writing the same wav.
*Test:* two `main()` calls under a shared lock dir; assert exactly one recorder pid.

### P9 — Explicit dependency preconditions
Missing a hard prerequisite (no recorder at START) fails with a precise, actionable
message naming the tool and exit 1 — never a Python traceback to nowhere.
*Test:* PATH stripped of recorders; assert notify text + exit 1.

### P10 — Backend resilience (fallback ladder)
local(cuda)→local(cpu)→api, each downshift logged with reason. A single unavailable layer
never aborts if a lower layer can serve.
*Violation:* CUDA init error crashes instead of retrying on cpu.
*Test:* inject a cuda-init exception; assert cpu path taken and logged.

### P11 — Config never fatal
A malformed/absent config or prompt file logs a warning and proceeds with defaults.
*Test:* point config at garbage TOML; assert defaults used, exit 0.

## Agent notes
> P3 and P5 are the two that make or break trust. Give them dedicated regression tests
> that run on every change, not just once.

## Related files
- `properties/edge-cases.md` — the boundary inputs (T-entries) that stress P5/P8.
- `spec/error-taxonomy.md` — the E-entries these properties defend against.
