---
id: arch-0001
type: decision
summary: STT is a pluggable Backend; default is local faster-whisper on GPU with a cuda→cpu→api fallback ladder.
domain: architecture
last-updated: 2026-07-03
depends-on: [external-faster-whisper-blackwell, external-openai-transcription-api]
related: [arch-overview, properties-functional]
---
# ADR 0001 — Pluggable STT, local default, API fallback

## Context
The user has an RTX 5060 Ti 16 GB (Blackwell) and wants "talk at any moment": low latency,
private, no per-use cost favour **local**. But Blackwell (sm_120) is bleeding edge — INT8
crashes, PyTorch stable lacks sm_120 kernels, CTranslate2/cuDNN versions matter
(`external/faster-whisper-blackwell.md`). A pure-local bet risks an unusable tool if the
GPU stack fights back; a pure-API bet throws away the GPU, privacy, and offline use.

## Decision
Make STT a `Backend` Protocol with two implementations and an automatic **fallback ladder**:
`local(cuda) → local(cpu) → api`. Default `backend=local`, `compute_type=float16`,
`model=large-v3-turbo`. `resolve_backend()` returns the first `available()` layer; each
downshift is logged with its reason (P10). The user can pin any layer via flag/env/config.

## Consequences
- **+** Ships working from day one: if Blackwell CUDA misbehaves, cpu or api still serves.
- **+** Riskiest unknown is isolated behind one class and proven first (plan Step 1).
- **+** pangolin (no GPU) uses the same code via config (NF5).
- **−** Two code paths to maintain and test; mitigated by the small Protocol surface.
- **−** Silent downshift could mask a broken GPU → every downshift is logged/notified.

## What this means for implementers
- Never top-level `import faster_whisper`; lazy-import inside `LocalBackend` so the api
  path doesn't pay for (or break on) it.
- On Blackwell, force `compute_type=float16`; if `int8` is ever requested there, log and
  override (E6). Verify CTranslate2 ≥ 4.5.0 at runtime.
- The api backend reuses revisor's keyring key (`service=revisor key=api-key`) and env
  `OPENAI_API_KEY`; it must run without faster-whisper installed (NF3).

## Related files
- `external/faster-whisper-blackwell.md` — the concrete version/precision constraints.
- `external/openai-transcription-api.md` — the api backend contract.
