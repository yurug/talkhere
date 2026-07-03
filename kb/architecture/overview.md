---
id: arch-overview
type: concept
summary: Module structure — a thin orchestrator over two pluggable interfaces (STT backend, delivery sink) plus recorder and feedback helpers.
domain: architecture
last-updated: 2026-07-03
depends-on: [spec-algorithms]
related: [arch-0001, arch-0002, arch-0003]
---
# Architecture overview

Single Python file `talkhere.py` (KISS, revisor-style), internally organised as a thin
orchestrator over small, testable units. Not split into a package unless it outgrows
~400 lines. Dependency injection via parameters/factories so tests supply fakes.

## Dependency graph

```
                    main(argv)
                       │  parse flags, load config, set up log
                       ▼
                 orchestrator (the toggle state machine — spec/algorithms.md)
        ┌──────────────┼───────────────┬────────────────┬───────────────┐
        ▼              ▼               ▼                ▼               ▼
   recorder        Backend          Sink            feedback         state
 (pw-record/     (transcribe)     (deliver)       (notify/sound)   (recording.json
  arecord)                                                          + flock)
        │              │               │
        │        ┌─────┴─────┐   ┌─────┼──────┐
        │     Local        Api  Type  Paste  Clipboard
        │  (faster-whisper)(OpenAI)(xdotool)(xdotool+clip)(xclip)
```

## Interfaces (the two pluggable seams)

```python
class Backend(Protocol):
    def transcribe(self, wav_path: str, lang: str) -> str: ...   # "" = no speech
    def available(self) -> bool: ...                             # for the fallback ladder

class Sink(Protocol):
    def deliver(self, text: str) -> None: ...
    def available(self) -> bool: ...
```

- **Backends:** `LocalBackend` (faster-whisper; cuda→cpu internal fallback),
  `ApiBackend` (OpenAI transcription via curl/stdlib). A `resolve_backend(cfg)` builds the
  fallback ladder local→api and returns the first `available()`.
- **Sinks:** `TypeSink` (xdotool type, Unicode-safe — the accent path), `PasteSink`
  (set clipboard + send paste key), `ClipboardSink` (xclip only). `resolve_sink(cfg)`
  degrades `type`→`clipboard` when xdotool is absent (P7).

## Support units
- **recorder** — spawns/stops the detached capture process; owns WAV finalisation (T3).
- **state** — read/write/clear `recording.json`, `flock` guard, stale-pid recovery (P8/E9).
- **feedback** — `cue_start/stop/done` + `notify`, all best-effort (never raise).
- **config** — precedence resolver (flag>env>file>default); never fatal (P11).
- **log** — append timestamped line; secret-safe (NF6).

## Why one file with internal seams (not a package, not one big main)
- **One file** keeps install trivial (`cp talkhere.py ~/.local/bin/talkhere`), like revisor.
- **Seams** (Protocols + factories) let the risky parts (LocalBackend, TypeSink) be unit-
  tested with fakes and swapped, which is exactly where the project's uncertainty lives.

## Agent notes
> The orchestrator must depend only on the `Backend`/`Sink` Protocols and the recorder/
> state helpers — never import faster-whisper at module top level (that would make the api
> backend pay for a heavy, possibly-broken import). Lazy-import inside `LocalBackend`.

## Related files
- `architecture/decisions/0001-pluggable-stt-local-default.md`
- `architecture/decisions/0002-toggle-trigger-lockfile.md`
- `architecture/decisions/0003-text-delivery-xdotool-type.md`
