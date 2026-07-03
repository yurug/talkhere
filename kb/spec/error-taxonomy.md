---
id: spec-error-taxonomy
type: spec
summary: Every failure talkhere can hit, when it occurs, the user-facing signal, and the exit code.
domain: reliability
last-updated: 2026-07-03
depends-on: [spec-algorithms, spec-cli-and-config]
related: [properties-edge-cases]
---
# Error taxonomy

Principle: **fail loud to the user, fail logged to the file, never inject garbage.**
Every error both appends to `~/.talkhere.log` and (when it affects the user) fires a
`notify-send`. talkhere is invoked from a hotkey with no visible terminal, so a silent
`stderr` is invisible — the notification IS the UI.

| ID | Condition | When | User signal | Exit | Property |
|----|-----------|------|-------------|------|----------|
| E1 | No injection tool (`xdotool` absent, `type`/`paste` sink) | STOP, deliver | notify "install xdotool"; fall back to `clipboard` sink so text isn't lost | 0 | P7 |
| E2 | No audio capture tool | START | notify "no recorder (pw-record/arecord)" | 1 | P9 |
| E3 | No audio device / mic muted | STOP: wav is silence/too short | notify "nothing captured" | 0 | P5 |
| E4 | Empty transcription (backend returns "") | STOP, after transcribe | notify "no speech recognised" | 0 | P5 |
| E5 | Local backend unavailable (import fails, model missing, CUDA init fails) | STOP, transcribe | log reason; auto-fall-back: cuda→cpu, then local→api if configured | 0/1 | P10 |
| E6 | Blackwell INT8 crash (`cuBLAS NOT_SUPPORTED`) | STOP, transcribe | should be prevented by compute_type=float16; if seen, log + force float16 retry | 0 | P10 |
| E7 | API backend, no key | STOP, transcribe | notify "no OpenAI key (keyring/env)" | 1 | P-sec |
| E8 | API backend, network/HTTP error | STOP, transcribe | log status+body; notify "transcription failed" | 1 | — |
| E9 | Stale state file (recorder pid dead) | START/STOP | treat as idle: clean stale state, log "recovered stale lock", proceed | 0 | P8 |
| E10 | Double-press race (two starts) | START | second caller blocks on flock; sees state now present → becomes STOP | 0 | P8 |
| E11 | Recorder didn't finalise WAV (killed too hard) | STOP | SIGINT-then-wait avoids it; if header bad, log + notify "recording corrupt" | 0 | T3 |
| E12 | Accented text mis-injected (`é`→`e`, dropped) | STOP, `type` sink | not silently accepted: `type` sink uses a Unicode-safe path; regression-tested | — | P3 |
| E13 | Config/prompt file unreadable or malformed TOML | startup | log + notify "bad config, using defaults"; never abort on config | 0 | P11 |

## Fallback ladder (resilience, P10)

```
backend: local(cuda) ──fail──▶ local(cpu) ──fail/absent──▶ api ──no key/net──▶ hard error E7/E8
sink:    type ──tool absent──▶ clipboard (text preserved, user pastes) ; notify either way
```

Every downshift is logged with its reason so a degraded run is diagnosable, not mysterious.

## Agent notes
> The cardinal sin is injecting wrong or empty text (P5, P6). When in doubt, prefer the
> clipboard sink (text recoverable) over typing something uncertain, and prefer notifying
> "nothing captured" over emitting noise. A no-op is always a safe outcome.

## Related files
- `properties/edge-cases.md` — T-entries these map to (silence, double-press, corrupt wav).
- `spec/algorithms.md` — where in the pipeline each error arises.
