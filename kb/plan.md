---
id: plan
type: spec
summary: Incremental implementation plan — riskiest path first (local Whisper on Blackwell + accent injection), then the toggle UX, then resilience/polish.
domain: planning
last-updated: 2026-07-03
depends-on: [prd, spec-algorithms, properties-functional, external-faster-whisper-blackwell]
---
# Implementation plan

Ordered by **risk**, not ease. The whole project's uncertainty lives in two places —
(1) does local Whisper run acceptably on the Blackwell GPU, and (2) does accented text
inject faithfully — so Step 1 is a running slice straight through both. Steps 2–3 add the
real UX and resilience only after Step 1 proves the tool is viable.

## ⚠ The one open architectural tension (decide in Step 1)
talkhere is a short-lived process per utterance (revisor-style, zero idle footprint / NF2),
but loading a Whisper *large* model takes **seconds**, which would dominate stop→text
latency (NF1 ≤ 2 s). These pull against each other. Step 1 MEASURES it and picks:
- **(a)** per-invocation load with a fast model (`large-v3-turbo`/`small`) — simplest, may be enough;
- **(b)** an optional warm-model helper (tiny persistent transcriber the STOP path talks to)
  — hits latency but reintroduces a resident process (softens ADR 0002's "no daemon");
- **(c)** default to the `api` backend for latency, local for privacy — user picks per use.
This choice is a Step-1 acceptance criterion, surfaced to the user before Step 2.

## Step 0 — Provision the environment (needs user go-ahead; system change)
Not code, but blocking and irreversible-ish (installs). Do together, verify each:
- `sudo apt-get install -y xdotool` (MISSING now).
- Create `.venv`; `pip install faster-whisper`; confirm CTranslate2 ≥ 4.5.0, CUDA 12.8
  runtime + cuDNN 9 visible; first-run downloads `large-v3-turbo`.
- Smoke-test: `python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cuda', compute_type='float16')"` loads without `cuBLAS NOT_SUPPORTED` / missing-lib.
- **Acceptance:** the smoke-test prints model loaded on cuda. If it fails → fall to cpu/api
  and record the exact error in `external/faster-whisper-blackwell.md` (researched→verified).

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

## Step 2 — The toggle UX (state machine, recorder, cues)
Turn the `--once` slice into the real product:
- Toggle no-arg flow with `recording.json` + `flock`, detached `pw-record` (SIGINT-clean
  stop / T3), stale-pid recovery (E9/T4), `--stop`/`--cancel`/`--status`.
- Feedback: `cue_start/stop/done` (paplay + notify-send). Robust MIN_MS/silence guard (T1/T2).
- i3 binding + `~/.local/bin/talkhere` symlink (revisor pattern). i3blocks `--status` indicator.
- **Acceptance:** one hotkey starts/stops dictation with clear cues; double-press is safe (P8);
  a killed recorder self-heals; text lands in whatever window is focused.
- Properties: P1, P7 (degrade), P8, P9; NF2, NF6.

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
