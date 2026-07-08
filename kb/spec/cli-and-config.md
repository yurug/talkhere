---
id: spec-cli-and-config
type: spec
summary: The full CLI contract (flags, exit codes) and the config/env/file surface for talkhere.
domain: interface
last-updated: 2026-07-08
depends-on: [prd, spec-algorithms]
related: [spec-error-taxonomy]
---
# CLI contract, configuration, and files

## Invocation

`talkhere [FLAGS]` — with no flags, it **toggles** (see `spec/algorithms.md`).

| Flag | Effect | Notes |
|------|--------|-------|
| *(none)* | toggle: start if idle, else stop+transcribe+inject | the one bound to the hotkey |
| `--stop` | force the stop branch | for a second, distinct binding if wanted |
| `--cancel` | kill recorder, inject nothing | "oops, forget it" |
| `--lang fr\|en\|auto` | force language for this utterance | overrides config/auto-detect |
| `--backend local\|api` | pick STT backend for this run | overrides config default |
| `--sink type\|paste\|clipboard` | pick delivery for this run | overrides config default |
| `--status` | print `recording`/`idle`, exit 0 if idle else 1 | for i3blocks/scripts |
| `--once` | record a fixed N seconds then transcribe (no toggle) | scripting/testing convenience |
| `-v/--verbose` | also echo the transcript to stdout | debugging, piping |
| `-h/--help` | usage | |

### Exit codes
`0` success (incl. "nothing captured" — a valid no-op). `1` unrecoverable error
(no backend available, no audio device, injection tool missing). `130` SIGINT.
`--status` uses `0`=idle, `1`=recording as a boolean for shell tests.

## Configuration precedence (highest wins)

1. Command-line flag.
2. Environment variable.
3. Config file `~/.config/talkhere/config.toml`.
4. Built-in default.

### Environment variables

| Var | Default | Meaning |
|-----|---------|---------|
| `TALKHERE_BACKEND` | `local` | `local` (faster-whisper) or `api` (OpenAI) |
| `TALKHERE_SINK` | `type` | `type` / `paste` / `clipboard` |
| `TALKHERE_LANG` | `auto` | `auto` / `fr` / `en` |
| `TALKHERE_MODEL` | `large-v3-turbo` | local model name (see external/faster-whisper) |
| `TALKHERE_COMPUTE` | `float16` | CTranslate2 compute_type — **do not set int8 on Blackwell** |
| `TALKHERE_DEVICE` | `cuda` | `cuda` / `cpu` (auto-falls back to cpu if cuda init fails) |
| `TALKHERE_API_MODEL` | `whisper-1` | OpenAI transcription model for the api backend |
| `OPENAI_API_KEY` | — | api backend key; else the keyring lookup below |
| `TALKHERE_KEYRING_SERVICE` | `talkhere` | GNOME keyring `service` for the api key |
| `TALKHERE_KEYRING_KEY` | `api-key` | GNOME keyring `key` attribute for the api key |
| `TALKHERE_TRAILING_SPACE` | `1` | append one space after injected text |
| `TALKHERE_KEEP_WAV` | `0` | keep the utterance wav for debugging |

### Config file (all keys optional; TOML)

```toml
backend = "local"           # local | api
sink = "type"               # type | paste | clipboard
lang = "auto"               # auto | fr | en
trailing_space = true
[local]
model = "large-v3-turbo"
device = "cuda"             # falls back to cpu on cuda failure
compute_type = "float16"    # int8 crashes on sm_120 Blackwell
[api]
model = "whisper-1"
[sink.type]
key_delay_ms = 8            # xdotool inter-key delay (0 can drop chars)
[sink.paste]
paste_key = "ctrl+v"        # per-app override, e.g. ctrl+shift+v for terminals
```

## On-disk files

| Path | Purpose | Lifetime |
|------|---------|----------|
| `~/.config/talkhere/config.toml` | user config | persistent, git-personal |
| `~/.talkhere.prompt` | Whisper `initial_prompt` vocabulary bias | persistent |
| `~/.talkhere.log` | timestamped append log (mirrors revisor) | grows; user-managed |
| `${XDG_RUNTIME_DIR:-/tmp}/talkhere/recording.json` | state/lock (idle=absent) | per utterance |
| `${XDG_RUNTIME_DIR:-/tmp}/talkhere/utterance-*.wav` | in-progress audio | deleted after inject |

## Agent notes
> `--status`'s inverted exit code (0=idle) is deliberate so `talkhere --status && echo idle`
> reads naturally. Document it in `--help`. Never fetch the API key from the config file
> or environment dumps into the log (P-security).

## Related files
- `spec/algorithms.md` — what each flag does to the state machine.
- `external/openai-transcription-api.md` — the api backend key/model behaviour.
