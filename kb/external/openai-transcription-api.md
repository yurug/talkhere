---
id: external-openai-transcription-api
type: external
summary: The OpenAI audio-transcription endpoint for the api backend — request shape, key sourcing (reuse revisor keyring), language param, and cost/latency notes.
domain: external-dependency
last-updated: 2026-07-08
related: [arch-0001, spec-cli-and-config]
---
# OpenAI transcription API (the `api` backend)

The guaranteed-works fallback and the only backend on machines without a usable GPU.
Mirrors how revisor calls OpenAI: `curl` + stdlib JSON, key from keyring/env — **no SDK
dependency** (keeps NF3: api backend runs without faster-whisper or `openai` installed).

## Endpoint
`POST https://api.openai.com/v1/audio/transcriptions` — multipart form upload.
```
# Auth header via curl's stdin config (-K -), NOT argv, so the key never shows in `ps`:
printf 'header = "Authorization: Bearer %s"\n' "$KEY" | \
curl -sS -K - https://api.openai.com/v1/audio/transcriptions \
  -F model=whisper-1 \
  -F "language=fr" \        # omit for auto-detect (P4)
  -F "response_format=text" \
  -F file=@<wav_path>
```
**Verified live 2026-07-08:** jfk.wav → exact transcript in ~2.3 s. The `-K -` (key on
stdin) form is what talkhere ships — it keeps the secret out of the process argv.
- `model`: `whisper-1` default (`TALKHERE_API_MODEL`); newer `gpt-4o-transcribe` /
  `gpt-4o-mini-transcribe` are options if desired — same endpoint shape.
- `language`: ISO-639-1 (`fr`/`en`); omit for auto-detect. `response_format=text` returns
  the plain transcript (no JSON parsing needed for the simple path).
- `prompt` (optional form field): the `~/.talkhere.prompt` vocabulary bias (T9).

## Key sourcing (configurable, never hard-code)
Order: `OPENAI_API_KEY` env → GNOME keyring `secret-tool lookup service <S> key <K>`, where
`S`/`K` default to `talkhere`/`api-key` and are overridable via `TALKHERE_KEYRING_SERVICE` /
`TALKHERE_KEYRING_KEY`. (The author reuses their `revisor` keyring key by exporting
`TALKHERE_KEYRING_SERVICE=revisor`.) No key → E7 (exit 1). Key never logged; passed to curl
via stdin, not argv.

## Runtime behaviour / budget
- One HTTP request per utterance. Cost is per-audio-minute; short dictations are cheap but
  **non-zero** and the audio **leaves the machine** — hence local is the privacy default (NF4).
- Latency = upload + server compute, typically ~1–2 s for short clips; network-bound.
- Errors: surface HTTP status + body to the log; notify "transcription failed" (E8).
  Handle 401 (bad key), 429 (rate limit), 5xx (retry once) minimally.

## Agent notes
> Keep this backend dependency-free (curl + stdlib) so a fresh machine can dictate via API
> with zero pip installs — the fastest path to a working tool while the local GPU stack is
> being sorted. This is what makes the Step-1 vertical slice safe to demo even if Blackwell
> fights back.

## Related files
- `architecture/decisions/0001-pluggable-stt-local-default.md` — where api sits in the ladder.
- `../../../perso/dev/revisor/revisor.py` — the proven curl+keyring pattern to mirror.
