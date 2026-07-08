#!/bin/bash
# Live P3 regression (kb/properties/functional.md): verify the `type` sink injects accented
# French + em-dash + emoji BYTE-EXACT into a focused X11 window. Needs a live X session with
# xdotool + python3-tk; pops a small window for ~1s. Safe: it only XTEST-types once the
# active window is confirmed to be our own 'talkhere-p3' capture window, and restores focus.
#
# Usage:  tools/p3_livetest.sh            # run under whatever layout is active
# Verified 2026-07-08 on pangoline (xdotool 3.20, us/QWERTY): RESULT P3_PASS_FULL.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
EXPECTED='Café — déçu, ça va ? 🙂'
OUT="$(mktemp)"; rm -f "$OUT"

ORIG=$(xdotool getactivewindow 2>/dev/null || true)
python3 "$HERE/p3_capture.py" "$OUT" &
CAP=$!

WID=$(xdotool search --sync --name '^talkhere-p3$' 2>/dev/null | tail -1)
xdotool windowactivate --sync "$WID" 2>/dev/null
if [ "$(xdotool getactivewindow getwindowname 2>/dev/null || true)" = "talkhere-p3" ]; then
    printf '%s' "$EXPECTED" | xdotool type --clearmodifiers --delay 12 --file -
    xdotool key --clearmodifiers Return
else
    echo "SAFETY ABORT: could not focus the capture window — not typing"; kill "$CAP" 2>/dev/null || true
fi
wait "$CAP" 2>/dev/null || true
[ -n "$ORIG" ] && xdotool windowactivate "$ORIG" 2>/dev/null || true

GOT="$(cat "$OUT" 2>/dev/null || true)"; rm -f "$OUT"
echo "EXPECTED: $EXPECTED"
echo "GOT     : $GOT"
if [ "$GOT" = "$EXPECTED" ]; then echo "RESULT: P3_PASS_FULL"; exit 0
else echo "RESULT: P3_FAIL (or emoji-only diff — inspect above)"; exit 1; fi
