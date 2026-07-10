---
id: prd
type: spec
summary: Product requirements — talkhere lets you dictate text into any focused X11 window via a single toggle hotkey.
domain: product
last-updated: 2026-07-10
depends-on: [glossary]
related: [spec-algorithms, properties-functional]
---
# Product Requirements — talkhere

## One-liner
Press a hotkey, speak, and your words are typed into whatever window has focus.

## User stories

- **U1 — Dictate into the terminal.** I'm in a shell, I press `$mod+Shift+d`, I say a
  command or a commit message, I press it again, and the text appears at the prompt.
- **U2 — Dictate into emacs / a browser / a chat.** Same hotkey, text lands at point
  in the focused app. No app-specific setup.
- **U3 — Bilingual.** I speak French with accents (`é à ç …`) or English; the injected
  text is correct in either language, and I can force a language when auto-detect slips.
- **U4 — Bias jargon.** I keep a small vocabulary file so names like "Nomadic Labs",
  "OCaml", "Tezos" transcribe correctly.
- **U5 — Know what's happening.** An audible/visual cue tells me recording started,
  stopped, and when the text is ready — I never stare at nothing wondering.
- **U6 — Fails safe.** If the mic is muted or I said nothing, I get a clear signal and
  nothing garbage is typed.

## Commands (see `spec/cli-and-config.md` for the full contract)

```bash
talkhere              # TOGGLE: start recording if idle, else stop+transcribe+inject
talkhere --lang fr    # force French for this utterance (overrides auto-detect)
talkhere --stop       # explicit stop (same as toggle-while-recording)
talkhere --cancel     # abort an in-progress recording, inject nothing
talkhere --backend api | local     # override the STT backend for this run
talkhere --sink type | paste | clipboard   # override delivery
talkhere --status     # print idle|recording and exit 0/1 (for i3blocks)
```

Primary use is a single i3 binding on the no-arg toggle form; flags are for power use.

## Non-functional expectations

- **Latency:** for a ~5 s utterance on the local GPU backend, stop→text ≤ ~2 s
  (target ≤ 1 s). API backend bounded by network.
- **Footprint:** no daemon required. A recording is a plain background `pw-record`
  process tracked by a PID file; idle talkhere consumes nothing.
- **Deps:** stdlib Python + system tools (`pw-record`/`arecord`, `xdotool`,
  `secret-tool`, `notify-send`, `paplay`). `faster-whisper` only for the local backend.
- **Portability:** must run on pangoline (GPU) and pangolin (no GPU → api/CPU backend).

## Out of scope (v1)

- Wayland *typing* at the cursor (`ydotool`/`wtype`) — the `type`/`paste` sinks stay X11
  (xdotool). **Wayland clipboard delivery IS supported** (2026-07-10): the `clipboard` sink
  is session-aware and uses `wl-copy` on Wayland, so `--sink clipboard` works there and
  feeds clipboard managers like KDE Klipper. On Wayland the default `type` sink degrades to
  this clipboard path automatically (P7).
- Streaming / live-as-you-speak transcription. v1 is record-then-transcribe.
- Voice commands / editing by voice ("delete that", "new line" macros) beyond literal
  punctuation Whisper already produces.
- A GUI, tray icon, or settings app. Config is a file.
- LLM post-processing of the transcript (that is revisor's job; the two compose —
  dictate with talkhere, then polish the selection with revisor).

## Agent notes
> The riskiest requirements are U3 (accents through key simulation) and the local
> backend on Blackwell. The plan's Step 1 proves both before anything else is built.

## Related files
- `spec/algorithms.md` — how a toggle becomes record→transcribe→inject.
- `properties/functional.md` — the invariants these stories imply (P1…).
- `architecture/overview.md` — how backends and sinks are wired.
