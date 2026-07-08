---
id: plan
type: spec
summary: Incremental implementation plan — riskiest path first (local Whisper on Blackwell + accent injection), then the toggle UX, then resilience/polish.
domain: planning
last-updated: 2026-07-08
depends-on: [prd, spec-algorithms, properties-functional, external-faster-whisper-blackwell]
---
# Implementation plan

Ordered by **risk**, not ease. The whole project's uncertainty lives in two places —
(1) does local Whisper run acceptably on the Blackwell GPU, and (2) does accented text
inject faithfully — so Step 1 is a running slice straight through both. Steps 2–3 add the
real UX and resilience only after Step 1 proves the tool is viable.

## ✅ The one architectural tension (RESOLVED 2026-07-08 with measurement)
talkhere is short-lived per utterance (zero idle footprint / NF2) vs. Whisper model load
taking seconds (NF1 ≤ 2 s). **Measured:** load ~2.2 s + transcribe ~1.3 s (5 s clip).
**Decision:** v1 uses **(a) per-invocation load** (`large-v3-turbo`, ~3.5 s stop→text, no
daemon) — usable and honours NF2. **(b)** an optional `--serve` warm helper (~1.3 s) is the
documented upgrade, deferred unless the user asks. LocalBackend keeps load/transcribe
separable so `--serve` can reuse them. See `external/faster-whisper-blackwell.md`.

## Step 0 — Provision the environment  ✅ DONE 2026-07-08 (GPU path verified)
- **faster-whisper 1.2.1 + ctranslate2 4.8.1 + nvidia-cudnn-cu12 9.24 + nvidia-cublas-cu12
  12.9** in `.venv` (user-space, no sudo). Driver 580.105.08 (CUDA 13.0-capable).
- **Smoke test PASSED:** float16 `large-v3-turbo` on cuda transcribed jfk.wav to exact
  ground-truth text (lang=en p=0.96). The cuBLAS pip pkg + `LD_LIBRARY_PATH` recipe are now
  recorded (verified) in `external/faster-whisper-blackwell.md`.
- **Recorder verified:** `pw-record` + SIGINT finalises a 16 kHz mono WAV (T3/E11).
- **REMAINING (user, needs sudo):** `sudo apt-get install -y xdotool` for the `type` sink.
  Until then Step 1 tests the record→transcribe half and the `clipboard` sink; the `type`/P3
  accent test runs once xdotool is present.

## Step 1 — Vertical slice through the riskiest path
Build the minimum runnable `talkhere --once <secs>`: record a fixed clip → `LocalBackend`
(faster-whisper, cuda, float16) → `TypeSink` (xdotool `type --file -`) into the focused window.
- **Riskiest sub-task first:** transcribe a fixture wav on the GPU and MEASURE stop→text incl.
  model load (NF1). Decide model-load strategy (a/b/c above) from the number.
- Then the **P3 accent regression**: round-trip "Café — déçu, ça va ? 🙂" into a scratch
  xterm under QWERTY *and* AZERTY; assert byte-equality. If `type` fails accents → default
  sink becomes `paste`; update ADR 0003.
- Wire the `local→api` guard so the slice still demos if cuda dies (P10).
- **Acceptance / definition of done:** from a shell, `talkhere --once 4` lets me speak one
  accented French sentence and see it typed correctly at the cursor; latency number recorded;
  model-load decision made. **Biggest unknown:** "does float16 large-v3-turbo load+run fast
  enough on sm_120?" — proven here or the plan pivots to api-default.
- Properties: P2, P3, P4, P5 (empty guard), P6; NF1, NF4.
- **Status 2026-07-08 — DONE.** `talkhere.py` implements `--once`, the Local/Api backends,
  all three sinks, feedback, logging, config; 13 unit tests + a GPU integration test pass.
  Verified live: record→GPU-transcribe→clipboard delivers the exact transcript; P5
  empty-guard fires on silence. **P3 VERIFIED live** (`tools/p3_livetest.sh`): `type` sink
  injected "Café — déçu, ça va ? 🙂" byte-exact (accents + em-dash + emoji) under us/QWERTY
  → the `type` default stands (no pivot to `paste`). AZERTY not force-switched to avoid
  clobbering the dual-layout config; xdotool remapping is layout-independent.

## Step 2 — The toggle UX (state machine, recorder, cues)
Turn the `--once` slice into the real product:
- Toggle no-arg flow with `recording.json` + `flock`, detached `pw-record` (SIGINT-clean
  stop / T3), stale-pid recovery (E9/T4), `--stop`/`--cancel`/`--status`.
- Feedback: `cue_start/stop/done` (paplay + notify-send). Robust MIN_MS/silence guard (T1/T2).
- i3 binding + `~/.local/bin/talkhere` symlink (revisor pattern). i3blocks `--status` indicator.
- **Acceptance:** one hotkey starts/stops dictation with clear cues; double-press is safe (P8);
  a killed recorder self-heals; text lands in whatever window is focused.
- Properties: P1, P7 (degrade), P8, P9; NF2, NF6.
- **Status 2026-07-08 — code DONE; desktop wiring pending.** `talkhere.py` has the toggle
  state machine (`recording.json` + `flock`), detached START/`stop_recorder_pid` (SIGINT),
  `--stop`/`--cancel`/`--status`, stale-pid recovery. 17 unit tests pass (P1/P8/E9 + P4 lang
  from state). Verified live: START→--status(recording)→--cancel→idle; a seeded STOP
  transcribed jfk.wav→clipboard; a dead-pid state self-healed. **Remaining:**
  `~/.local/bin/talkhere` venv wrapper, i3 `bindsym $mod+Shift+d` (approved) + optional
  cancel binding, i3blocks `--status` indicator — a live-desktop change (also sync dotfiles
  bootstrap.sh + MACHINE.md per ~/CLAUDE.md).

## Step 3 — Resilience, config, sinks, polish
- Full fallback ladder cuda→cpu→api (P10); `config.toml` + env precedence (P11);
  `~/.talkhere.prompt` vocab bias (T9); `--lang`/`TALKHERE_LANG` override (P4).
- All sinks: `paste` (per-app paste key) + `clipboard`; degrade path (P7).
- Logging pass (NF6, secret-safe); pangolin cpu/api portability check (NF5).
- Full test suite: every P/T named-test; Xvfb integration for P3; run Phase-5 audit gate.
- **Acceptance:** `runbooks/audit-checklist.md` passes 0 criticals; runs on both machines.

## Notes
- 3 code steps (+ Step 0 provisioning, + Phase-5 audit) — within the ADK 3–4 limit. If any
  step won't converge in ~7 iterations, stop and split.
- Each step ends committed + validated before the next (per ~/CLAUDE.md workflow).
