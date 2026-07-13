---
id: spec-algorithms
type: spec
summary: The toggle state machine and the record→transcribe→inject pipeline, including the lock-file protocol.
domain: core
last-updated: 2026-07-13
depends-on: [glossary, prd]
refines: [prd]
related: [spec-error-taxonomy, properties-functional, arch-overview]
---
# Algorithms — toggle state machine and pipeline

talkhere is a **single, short-lived process** each time it runs. State between the
"start" invocation and the "stop" invocation lives entirely in the **runtime dir**
`${XDG_RUNTIME_DIR:-/tmp}/talkhere/`. There is no daemon.

## State model

Two observable states, decided by the presence of the **state file** `recording.json`:

```
        talkhere (no args)                 talkhere (no args)
 IDLE ───────────────────────▶ RECORDING ───────────────────────▶ IDLE
   ▲   start pw-record,            │    stop pw-record, transcribe,   │
   │   write recording.json        │    inject text, delete state     │
   └──────────────── talkhere --cancel (kill recorder, delete state, inject nothing)
```

`recording.json` holds: `{ "pid": <recorder pid>, "wav": "<path>", "started": <epoch>,
"lang": "<fr|en|auto>", "window": "<xdotool id focused at START>" }`. Its **presence is the
lock**; its absence means idle. `window` is the delivery target (P12): focus will usually have
moved by STOP, and the transcript must go back where the user began, not follow the cursor.

## The toggle algorithm (no-arg invocation)

```
1. acquire_lock():                          # flock on runtime/talkhere.lock — see P8
   prevents two near-simultaneous hotkey presses from both "starting".
2. if state file ABSENT  → START:
     a. ensure runtime dir exists
     b. wav = runtime/utterance-<started>.wav
     c. spawn recorder detached: pw-record --channels 1 --rate 16000 <wav>
        (fallback: arecord -f S16_LE -r 16000 -c 1 <wav>) — see external/audio-capture
     d. window = xdotool getactivewindow          # the delivery target (P12)
     e. write recording.json {pid, wav, started, lang, window}
     f. cue_start(): play start sound + notify "● recording"
     g. exit 0    (the recorder keeps running in the background)
3. else                  → STOP:
     a. read recording.json
     b. stop the recorder GRACEFULLY: SIGINT the pid, wait ≤1s for flush, then SIGTERM.
        (SIGINT lets pw-record/arecord finalise the WAV header — see edge case T3)
     c. cue_stop(): play stop sound + notify "… transcribing"
     d. if wav missing or shorter than MIN_MS (≈300ms of audio) → abort, notify
        "nothing captured", delete state, exit 0   (P5: never inject on empty)
     e. text = backend.transcribe(wav, lang)       # local or api — arch/overview
     f. text = postprocess(text)                   # trim, collapse ws, honour trailing-space cfg
     g. if text non-empty → deliver to st.window   # refocus the START window, hold focus
        (windowactivate --sync + park the pointer inside it for the whole typing burst so
        focus-follows-mouse cannot steal it); if that window is gone → clipboard, type NOTHING
        else → notify "no speech recognised"
     h. delete recording.json and the wav (unless TALKHERE_KEEP_WAV) 
     i. cue_done(): notify "✓ <first 40 chars>"
     j. exit 0
4. release_lock()  (always, via finally)
```

`--stop` forces the STOP branch; `--cancel` reads state, kills the recorder, deletes
the wav + state, injects nothing. `--status` prints `recording`/`idle` and exits.

## Why toggle + lock file (not a daemon, not push-to-talk)

- **No daemon** → nothing to crash, autostart, or leak; matches revisor's zero-resident
  footprint. The OS process table *is* our state (recorder pid), the state file names it.
- **Toggle** maps cleanly onto a single i3 `bindsym` (a plain keypress). Push-to-talk
  needs press+release (`--release`) wiring and is awkward for long dictation; kept as a
  possible future sink of the same pipeline, not v1. See `decisions/0002`.
- **Lock file** closes the double-press race (P8): two hotkeys within milliseconds must
  not both start recorders.

## Transcription pipeline (STOP step e–g), backend-agnostic

```
wav ──▶ backend.transcribe(wav, lang) ──▶ raw text
raw text ──▶ postprocess ──▶ clean text ──▶ sink.deliver(clean text)
```

- `lang` = `auto` (Whisper detect), or a forced `fr`/`en` (`--lang`, `TALKHERE_LANG`).
- `postprocess`: strip leading/trailing whitespace Whisper adds; optionally append one
  trailing space so consecutive dictations don't run together (config `trailing_space`);
  never alter interior content (P6: fidelity — talkhere transcribes, it does not edit).

## Agent notes
> The recorder MUST be spawned fully detached (new session, stdio to /dev/null) so the
> starting process can exit while recording continues. Losing the pid = orphan recorder.
> Store the pid in the state file AND cross-check `/proc/<pid>` before signalling (T4).

## Related files
- `spec/error-taxonomy.md` — every failure branch above and its user message.
- `properties/functional.md` — P5 (no empty inject), P6 (fidelity), P8 (no double-start).
- `external/audio-capture-pipewire.md` — exact recorder command and WAV finalisation.
- `architecture/overview.md` — the backend/sink interfaces this pipeline calls.
