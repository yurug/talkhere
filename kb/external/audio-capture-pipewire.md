---
id: external-audio-capture-pipewire
type: external
summary: Recording a 16 kHz mono WAV for Whisper with pw-record (PipeWire) or arecord (ALSA), and finalising the header cleanly on stop.
domain: external-dependency
last-updated: 2026-07-03
related: [spec-algorithms, properties-edge-cases]
---
# Audio capture for talkhere

Whisper wants **16 kHz mono PCM**. Both recorders below produce a suitable WAV.
pangoline has PipeWire (`pw-record`, `pactl`) + ALSA (`arecord`) + `ffmpeg`/`sox`.

## Primary: pw-record (PipeWire, native on Debian 13)
```
pw-record --rate 16000 --channels 1 --format s16 <wav_path>
```
Runs until terminated. It writes a WAV; on a clean signal termination it finalises the
RIFF header (sizes). We spawn it detached and stop it on the toggle's STOP branch.

## Fallback: arecord (ALSA)
```
arecord -q -f S16_LE -r 16000 -c 1 -t wav <wav_path>
```
Used when `pw-record` is unavailable. Same detached-spawn/stop protocol.

## Stopping cleanly — the WAV-header gotcha (T3/E11)
A WAV written incrementally has header size fields that are only correct once the writer
finalises on exit. If we `SIGKILL`/`SIGTERM` mid-write, the header can be truncated/wrong
and Whisper may reject or mis-read it.
- **Protocol:** send **SIGINT** first (both pw-record and arecord treat it as a clean stop
  and flush/finalise), wait up to ~1 s for the process to exit, then escalate to SIGTERM,
  then SIGKILL only as last resort. Verify the resulting WAV opens with the stdlib `wave`
  module before transcribing; if not, report E11.

## Duration / silence guards (P5/T1/T2)
- Reject utterances shorter than **MIN_MS ≈ 300 ms** (an accidental double-tap) → "nothing
  captured", no transcription.
- Optional cheap silence check: read the WAV with stdlib `wave`, compute mean abs amplitude;
  below a floor → treat as silence. (faster-whisper's `vad_filter=True` also helps.)

## Device selection
Default device follows the PipeWire/ALSA default sink-source. If the wrong mic is picked,
it's a config concern, not code — document `pactl list sources` / `PULSE_SOURCE` /
`arecord -l` in the README troubleshooting. Do not hard-code a device.

## Agent notes
> Spawn the recorder with `start_new_session=True` and stdio redirected to DEVNULL so the
> "start" invocation can exit immediately while recording continues. Capture the child pid
> BEFORE writing recording.json; a lost pid orphans the recorder.

## Related files
- `spec/algorithms.md` — where START spawns and STOP stops the recorder.
- `properties/edge-cases.md` — T1 (too short), T2 (silence), T3 (header finalisation).
