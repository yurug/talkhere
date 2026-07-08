---
id: external-xdotool-x11-typing
type: external
summary: How to inject Unicode text with xdotool on X11 without mangling accents or dropping characters; the flags and layout gotchas.
domain: external-dependency
last-updated: 2026-07-08
related: [arch-0003, properties-functional]
---
# xdotool text injection on X11

**Status: VERIFIED on pangoline 2026-07-08 (xdotool 3.20, us/QWERTY).**
`xdotool type --clearmodifiers --delay 12 --file -` reading UTF-8 from stdin injected
"Café — déçu, ça va ? 🙂" **byte-exact** — accents, em-dash, and even the non-BMP emoji all
survived. So the accent risk (P3) is closed for the default `type` sink; reproduce with
`tools/p3_livetest.sh`. (AZERTY not force-tested to avoid clobbering the live dual-layout
config; xdotool remaps keysyms independent of the base layout, which is why it worked here.)

`xdotool` works only on X11 (our case: i3 on X11). It injects via XTEST. Two relevant verbs:
- `xdotool type <string>` — types characters (what we want for `TypeSink`).
- `xdotool key <keysym>` — presses named keys (used for the `paste` sink: `key ctrl+v`).

## Recommended invocation for TypeSink
```
xdotool type --clearmodifiers --delay <ms> --file -      # text on stdin
```
- `--file -` (or `--file <path>`): read the text to type from stdin/a file instead of argv.
  Avoids shell-quoting/escaping hazards and argv length limits for long dictations.
- `--clearmodifiers`: releases any held modifier (e.g. a stuck Shift from the hotkey) that
  would otherwise corrupt output, then restores it.
- `--delay <ms>`: inter-keystroke delay. **`0` can drop characters** in fast terminals;
  default xdotool is 12 ms. We expose `key_delay_ms` (default ~8) and tune in Step 1.

## Unicode / accents — the P3 risk
- `xdotool type` remaps needed characters into the X keymap on the fly, so it *can* emit
  characters not on the physical layout (accents, em-dash, emoji) — in principle
  layout-independent. In practice this is the flakiest area and depends on the active
  layout and Xkb state.
- **Known failure modes to test:** characters silently dropped; wrong glyph under an
  active AZERTY vs QWERTY layout (the user switches with Ctrl+Shift); dead-key composition
  interfering; emoji unsupported by the app font (renders tofu but bytes are correct).
- **Verification (Step 1, blocking):** round-trip "Café — déçu, ça va ? 🙂" into a scratch
  `xterm`, read it back, assert byte-equality — under BOTH the QWERTY and AZERTY layouts.
- **If it fails:** switch the default sink to `paste` (clipboard is set with the exact
  UTF-8, then `xdotool key ctrl+v`), which does not go through per-character key
  simulation and is Unicode-robust. Record the outcome in ADR 0003.

## PasteSink specifics
- Set clipboard with `xclip -selection clipboard` (already installed), then
  `xdotool key --clearmodifiers <paste_key>` where `paste_key` defaults to `ctrl+v` but is
  configurable (`ctrl+shift+v` for terminals, and emacs needs `ctrl+y` — hence per-app cfg).
- Trade-off: robust bytes, but the correct paste chord is app-specific → why `type` is the
  default and `paste` the escape hatch.

## Install
`sudo apt-get install -y xdotool` (currently MISSING on pangoline). Mirror this into the
README install steps and the machine bootstrap (per ~/CLAUDE.md system-change rule).

## Agent notes
> Do not build the string into the shell command. Always pipe via `--file -`. This both
> fixes quoting and is the safe path for arbitrary transcribed text (which may contain
> quotes, `$`, backticks, newlines).

## Related files
- `architecture/decisions/0003-text-delivery-xdotool-type.md` — the sink decision.
- `properties/functional.md` — P3 (accents), P7 (degradation to clipboard).
