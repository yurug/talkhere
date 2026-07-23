# Incident — silent transcription loss on a shared GPU (2026-07-23)

Reported by the user: "a recording was not transcribed". Three dictations that morning
produced no text, **no error, and no notification**. Two of them were multi-minute
work dictations. Root-caused, fixed, and turned into P13/E15/E16/T11 the same day.

## Evidence

`~/.talkhere.log`, three runs (09:30, 09:32, 09:36) share one signature — a model load
followed by nothing at all:

```
09:30:34 local: loaded large-v3-turbo on cuda/float16 in 7.00s
09:31:32 START recorder pid=882403          <- next event is a NEW recording
```

No `transcribed` line, no `delivered` line, and the wav still sitting in
`/run/user/1000/talkhere/` (it is only unlinked after a successful delivery).

GPU state at diagnosis time: **13.7 GB of 16.3 GB held** by docker llama.cpp servers
(`tezai-gpu`, `mock-serve`, up 9–12 days) plus `ollama`. Free: ~1.8 GB.
Measured talkhere footprint mid-inference: **1920 MiB**.

## Root cause (two layers)

1. **Environment:** free VRAM sat *between* the model size (~1.6 GB) and the full inference
   footprint (~1.9 GB). `WhisperModel(...)` therefore succeeded and the transcription then
   hit `CUDA failed with error out of memory`.
2. **Code (the real bug):** the P10 fallback ladder only wrapped the model **load**
   (`LocalBackend._load`), not `model.transcribe(...)`. The exception escaped
   `transcribe_and_deliver` → `main()`, which had **no catch-all** despite
   `conventions/code-and-testing.md` requiring one. Launched from an i3 hotkey, stderr goes
   nowhere: no log, no notification, and `_stop` never reached the point where the wav is
   kept or dropped — it simply died, leaving the audio in a directory `/run` wipes at logout.

## Fix (this commit)

- `main()` wraps `_dispatch()`: logs `FATAL` + traceback, notifies, exits 1 (E15).
- `transcribe_or_keep()` preserves the wav in `~/.talkhere/failed/` on exception or non-zero
  exit, bounded to the 5 most recent; `--retry-last` / `--file WAV` replay it (P13).
- `LocalBackend.transcribe()` retries on cpu/int8 when cuda fails **during inference**, not
  just at load (P10/E5).
- Pre-flight `nvidia-smi --query-gpu=memory.free` against `TALKHERE_MIN_VRAM_MB` (2300 MiB):
  under the floor, cuda is skipped entirely for cpu, logged and notified (E16).

## Recovery

Both orphaned wavs were re-transcribed intact (1033 and 566 characters) — no data was
actually lost, only invisible. That is precisely what `--retry-last` now automates.

## Lesson

A degradation ladder that covers *initialisation* but not *use* is a half ladder: a shared
resource can accept the handle and refuse the work. And any exit path a hotkey-launched tool
can take must be loud, because stderr is a black hole.
