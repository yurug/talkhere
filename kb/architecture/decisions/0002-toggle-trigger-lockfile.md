---
id: arch-0002
type: decision
summary: Recording is controlled by a single toggle hotkey backed by a runtime-dir state/lock file; no daemon, no push-to-talk in v1.
domain: architecture
last-updated: 2026-07-03
related: [spec-algorithms, arch-overview]
---
# ADR 0002 — Toggle trigger via runtime state file (no daemon)

## Context
The tool must be reachable "at any moment" from i3. Options for start/stop control:
(a) **toggle** — one hotkey alternates start/stop; (b) **push-to-talk** — hold key,
release to transcribe; (c) a resident **daemon** listening for a global hotkey. i3
`bindsym` is a plain keypress; `--release` exists but is fiddlier for long dictation.

## Decision
Use **toggle**, bound to a single i3 `bindsym`. State lives in
`${XDG_RUNTIME_DIR:-/tmp}/talkhere/recording.json`; **presence = recording**. A `flock`
serialises concurrent presses (P8). The recorder is a detached background process whose
pid is stored in the state file. **No daemon.**

## Consequences
- **+** Zero idle footprint (NF2); nothing to autostart or crash. The process table is
  the state; the file names the recorder.
- **+** Trivial i3 integration: `bindsym $mod+Shift+d exec --no-startup-id talkhere`.
- **+** Long dictations are natural (start, talk freely, stop) — no key to hold.
- **−** Toggle can desync if a process dies mid-way → stale-pid recovery makes it self-heal
  (E9/T4): a dead pid in the state file is treated as idle and cleaned.
- **−** No "hold to talk" muscle-memory; acceptable, and push-to-talk can later be added
  as a second binding calling the same pipeline with `--release` start/stop.

## What this means for implementers
- Spawn the recorder fully detached (`start_new_session=True`, stdio → /dev/null) so the
  starting process exits while recording continues.
- Always `flock` around the read-decide-write of the state file.
- On every entry, validate the stored pid against `/proc/<pid>` before trusting the state.

## Related files
- `spec/algorithms.md` — the exact START/STOP/CANCEL steps and the lock protocol.
