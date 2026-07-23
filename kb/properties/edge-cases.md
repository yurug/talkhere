---
id: properties-edge-cases
type: constraint
summary: Boundary conditions T1–T10 with expected behaviour, feeding the test suite.
domain: correctness
last-updated: 2026-07-23
related: [properties-functional, spec-error-taxonomy]
---
# Edge cases

| ID | Input / situation | Expected behaviour |
|----|-------------------|--------------------|
| T1 | Hotkey pressed, immediately pressed again (<300 ms of audio) | STOP branch sees wav below MIN_MS → "nothing captured", no inject (P5) |
| T2 | Pure silence for 10 s | backend returns "" or Whisper hallucination guard trips → "no speech" (P5); see note |
| T3 | Recorder killed with SIGTERM before WAV header flush | SIGINT-first + ≤1 s wait finalises header; else "recording corrupt" (E11) |
| T4 | State file present but recorder pid is dead (crash/reboot) | recognised as stale, cleaned, treated as IDLE, logged (E9) |
| T5 | Two rapid no-arg invocations | flock serialises; one starts, the other becomes STOP (P8/E10) |
| T6 | Very long utterance (2 min) | records fully; transcription may take longer but completes; NF1 bound is for ~5 s |
| T7 | Accented + emoji + em-dash text: "Café — déçu 🙂" | injected byte-exact via Unicode-safe path (P3) |
| T8 | Mixed FR/EN in one utterance under `auto` | Whisper picks dominant language; user can redo with `--lang` (acceptable) |
| T9 | `~/.talkhere.prompt` present with jargon list | passed as `initial_prompt`; biases spelling; empty/absent → no bias |
| T10 | CUDA present but OOM / driver mismatch at load | caught, fall back cpu→api, logged (P10/E5) |
| T11 | GPU shared with another workload: the model loads, then OOMs **during** inference | pre-flight skips cuda under the VRAM floor (E16); if it still fails, the cpu retry runs (E5) and, failing that, the audio is preserved for `--retry-last` (P13/E15) — never a silent loss |

## Note on T2 (silence hallucination)
Whisper models can hallucinate text ("Thank you.", "Sous-titres…") on silence. Guard:
(a) reject wavs shorter than MIN_MS; (b) optionally check mean absolute amplitude below a
floor → treat as silence; (c) `condition_on_previous_text=False` and a `no_speech_threshold`.
Document the chosen guard in the local backend and cover it with a silent-wav test.

## Related files
- `spec/error-taxonomy.md` — E-entries corresponding to these T-entries.
- `properties/functional.md` — P5/P8 that these cases exercise.
