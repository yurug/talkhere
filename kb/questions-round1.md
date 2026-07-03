# Ambiguity resolution — round 1

I asked four forking questions; you'd stepped away, so I locked in the **Recommended**
default for each (all revisable — each is a thin config point, not baked into the design).
Edit any answer below and I'll adjust the KB/plan before implementing.

## Decided-by-default (the four forks)

**D1. STT engine** → **local faster-whisper (GPU), pluggable, api fallback.**
Rationale: your RTX 5060 Ti + privacy + offline + no per-use cost. Blackwell risk absorbed
by the `local(cuda)→local(cpu)→api` ladder (ADR 0001). Flip with `--backend api`.

**D2. Trigger** → **toggle hotkey** (one i3 binding; press start / press stop). ADR 0002.

**D3. Delivery** → **`type` at cursor via xdotool**, degrading to clipboard if xdotool
absent; `paste`/`clipboard` sinks selectable. If Step-1 accent tests fail, default flips to
`paste` (ADR 0003).

**D4. Language** → **auto-detect**, with `--lang fr|en` / `TALKHERE_LANG` override.

## Open questions (proposed defaults — please confirm or change)

**Q5. Model-load latency vs "no daemon" (the real tension).**
A large model loads in seconds each invocation; that fights the ≤2 s latency target.
Default: *measure in Step 1 with `large-v3-turbo`; if too slow, offer an optional warm-model
helper (`--serve`) rather than making it always-on.* → Are you OK with an optional resident
helper for speed, or must it stay strictly no-daemon even at some latency cost?

**Q6. Whisper model.** Default `large-v3-turbo` (fast, strong FR+EN). Change to `large-v3`
(max accuracy, slower) or `medium`/`small` (faster/CPU)?

**Q7. Hotkey.** Default i3 `bindsym $mod+Shift+d` (d = dictate) for toggle, `$mod+Shift+f`
to force French. Your `$mod`? Any clash with existing bindings? (revisor uses
`$mod+Shift+Control+r`.)

**Q8. Where does talkhere live?** It's in `work/dev/talkhere`. revisor is in `perso/dev`.
Is talkhere personal (move to `perso/dev`) or a work tool (stay)? Publish to GitHub like
revisor (yurug/…), and under which account?

**Q9. Trailing space.** Default: append one space after injected text so consecutive
dictations don't run together. OK, or no trailing space?

**Q10. Feedback style.** Default: short `paplay` blips on start/stop + `notify-send`
(dunst) toasts, plus an i3blocks `●`/`○` indicator. Sounds too? Or notifications only?

**Q11. API key namespace.** Default: reuse revisor's keyring entry
(`service=revisor key=api-key`) + `OPENAI_API_KEY`. Or give talkhere its own
`service=talkhere` entry?

**Q12. Scope confirmations.** Confirm these v1 exclusions (PRD "Out of scope"): no Wayland,
no live-streaming transcription, no voice-command editing, no LLM post-processing (that's
revisor — the two compose). Anything here you actually want in v1?
