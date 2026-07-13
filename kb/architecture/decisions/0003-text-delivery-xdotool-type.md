---
id: arch-0003
type: decision
summary: Delivery is a pluggable Sink; default `type` via xdotool with a Unicode-safe path, degrading to clipboard; paste and clipboard sinks available.
domain: architecture
last-updated: 2026-07-13
depends-on: [external-xdotool-x11-typing]
related: [properties-functional, spec-error-taxonomy]
---
# ADR 0003 — Text delivery: xdotool `type` default, clipboard fallback

> **Status VERIFIED 2026-07-08:** the P3 risk this ADR hedges against did NOT materialise —
> `xdotool type --file -` injected "Café — déçu, ça va ? 🙂" byte-exact (accents, em-dash,
> emoji) under us/QWERTY (`tools/p3_livetest.sh`). The `type` default **stands**; the pivot
> to `paste` is not needed. `paste`/`clipboard` remain as selectable escape hatches (P7).
>
> **Update 2026-07-10 — Wayland clipboard:** `ClipboardSink` is now session-aware (uses
> `wl-copy` on Wayland, `xclip` on X11), so `--sink clipboard` works on Wayland/KDE and feeds
> clipboard managers like Klipper. `type`/`paste` stay X11 (xdotool); on Wayland the default
> `type` degrades to this clipboard path. This realises the "keep the sink pluggable" hedge
> without adding Wayland *typing* (which would need ydotool/uinput).
>
> **Update 2026-07-13 — delivery is TARGETED, not focus-following (P12):** XTEST sends every
> keystroke to whatever is focused *at that instant*, so the old behaviour typed into whatever
> window the user had drifted to by STOP — and could even split a sentence across windows when
> focus moved mid-burst (i3 enables `focus_follows_mouse` by default, so a mouse nudge sufficed).
> Delivery now refocuses the window captured at START (`windowactivate --sync`), verifies it, and
> parks the pointer inside it for the whole typing burst (restoring it after). If that window is
> gone we type **nothing** and fall back to the clipboard (E14). `xdotool type --window` would
> have made this trivial, but it uses XSendEvent and apps ignore those synthetic events —
> empirically confirmed — so controlling focus is the only reliable route.

## Context
"talk-to-type" implies text should appear at the cursor, hands-free, in any focused app.
Options: (a) **type** — `xdotool type` simulates keystrokes; universal across terminal/
emacs/GUI but can mangle accents/Unicode under an active QWERTY layout and drop chars if
too fast; (b) **paste** — set clipboard, send a paste keystroke; robust Unicode but the
paste shortcut differs per app (terminal `ctrl+shift+v` vs `ctrl+v` vs emacs `C-y`);
(c) **clipboard only** — revisor-style, user pastes manually; most robust, not hands-free.

The user is bilingual FR/EN — accent fidelity (P3) is non-negotiable.

## Decision
`Sink` Protocol with three implementations. Default **`type`**, implemented Unicode-safely:
feed text to `xdotool type --clearmodifiers --delay <key_delay_ms> --file -` (read from
stdin/file, not argv), which handles arbitrary UTF-8 without shell-quoting hazards. If
`xdotool` is absent, **degrade to `clipboard`** and notify (P7) — never lose text. `paste`
and `clipboard` are selectable via `--sink`/config for apps where typing misbehaves.

## Consequences
- **+** True hands-free dictation everywhere by default.
- **+** No text ever lost: the degrade path preserves it on the clipboard.
- **−** `type` remains the accent risk surface → P3 gets a dedicated round-trip regression
  test that MUST pass in Step 1 before anything else is built on top.
- **−** A per-key delay is needed to avoid dropped characters; exposed as `key_delay_ms`.

## What this means for implementers
- Prove P3 first: `TypeSink` round-trips "Café — déçu, ça va ? 🙂" into a scratch xterm and
  asserts byte-equality. If `xdotool type` can't do accents under the test layout, switch
  the DEFAULT to `paste` and record it here — do not ship a lossy default.
- Reset the keyboard layout expectation: `--clearmodifiers` avoids a held mod key
  corrupting output; verify behaviour with the AZERTY layout active too (user switches).

## Related files
- `external/xdotool-x11-typing.md` — the exact flags and known Unicode/layout gotchas.
- `properties/functional.md` — P3 (accents), P7 (degradation).
