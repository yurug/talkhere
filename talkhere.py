#!/usr/bin/env python3
"""talkhere — talk-to-type for Linux/X11.

Press a hotkey, speak, and the recognised text is injected at the cursor of the
focused window. Spoken-input sibling of revisor; KISS single script.

This file (Step 1 of kb/plan.md) implements the *vertical slice*: `--once N`
records a fixed clip, transcribes it (local faster-whisper on the GPU, or the
OpenAI API), and delivers the text through a pluggable sink (type / paste /
clipboard). The toggle state machine (Step 2) builds on this same machinery.

Spec:  kb/spec/algorithms.md (pipeline), kb/spec/cli-and-config.md (flags/config)
Deps:  kb/external/{faster-whisper-blackwell,xdotool-x11-typing,audio-capture-pipewire,
       openai-transcription-api}.md
Props: P2 inject-to-focus, P3 accent fidelity, P4 language, P5 never-inject-empty,
       P6 fidelity, P7 sink-degrade, P10 backend-fallback, P12 target window,
       P13 no silent failure / audio survives (kb/properties/functional.md)

Design decisions (see kb/architecture/):
- Backends and Sinks are small Protocols with factory resolvers that build a
  degradation ladder (local->api, type->clipboard). DI everywhere for testing.
- The local backend imports faster_whisper LAZILY and ctypes-preloads the pip
  cuDNN/cuBLAS so it works from any launch context (a hotkey has no LD_LIBRARY_PATH).
- Nothing here writes secrets to disk or the log; the API key is fetched at runtime.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
import wave
from pathlib import Path
from typing import Protocol

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
LOG_FILE = Path.home() / ".talkhere.log"
PROMPT_FILE = Path.home() / ".talkhere.prompt"        # Whisper initial_prompt (T9)
CONFIG_FILE = Path.home() / ".config" / "talkhere" / "config.toml"
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "talkhere"
STATE_FILE = RUNTIME_DIR / "recording.json"   # presence == recording (kb/spec/algorithms.md)
LOCK_FILE = RUNTIME_DIR / "talkhere.lock"     # flock serialises the toggle decision (P8)
# Audio whose transcription failed is moved OUT of the runtime dir (which /run wipes on
# logout) into the home dir, so a lost dictation is always recoverable (P13/E15).
FAILED_DIR = Path.home() / ".talkhere" / "failed"

MIN_MS = 300                    # utterances shorter than this are "nothing captured" (P5/T1)
SAMPLE_RATE = 16000             # Whisper wants 16 kHz mono
DEFAULT_MODEL = "large-v3-turbo"
FAILED_KEEP = 5                 # keep only the N most recent failed recordings (no growth)
# Measured peak on an RTX 5060 Ti: large-v3-turbo/float16 holds ~1920 MiB during inference
# (kb/external/faster-whisper-blackwell.md). Below this much FREE VRAM the model may load
# and then die mid-transcription, so we pre-empt that and go straight to CPU (E16).
MIN_FREE_VRAM_MB = 2300


# ---------------------------------------------------------------------------
# Logging and small helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    """Append a timestamped line to ~/.talkhere.log (NF6). Best-effort: logging must
    never take down the pipeline, so all errors are swallowed."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def whereis(cmd: str) -> bool:
    """True if `cmd` is on PATH. Used to gate every optional external tool."""
    return shutil.which(cmd) is not None


def _is_wayland() -> bool:
    """True on a Wayland session. talkhere types via xdotool (X11 only), so on Wayland only
    the clipboard sink works — and it must use wl-copy rather than xclip."""
    return (os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            or bool(os.environ.get("WAYLAND_DISPLAY")))


def _active_window() -> str | None:
    """X11 id of the currently focused window, or None. This is the *target* we remember at
    START so the transcript lands where the user began dictating (P12), not wherever focus
    happens to be seconds later when they stop."""
    if not whereis("xdotool"):
        return None
    try:
        r = subprocess.run(["xdotool", "getactivewindow"],
                           capture_output=True, text=True, timeout=2)
        wid = r.stdout.strip()
        return wid if r.returncode == 0 and wid else None
    except Exception:
        return None


def _window_exists(wid: str) -> bool:
    """True if the window still exists (the user may have closed it while dictating)."""
    try:
        r = subprocess.run(["xdotool", "getwindowname", wid],
                           capture_output=True, text=True, timeout=2)
        return r.returncode == 0
    except Exception:
        return False


def _mouse_location() -> tuple[str, str, str] | None:
    """(x, y, window_under_pointer) or None."""
    try:
        r = subprocess.run(["xdotool", "getmouselocation", "--shell"],
                           capture_output=True, text=True, timeout=2)
        if r.returncode != 0:
            return None
        v = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
        return v.get("X", ""), v.get("Y", ""), v.get("WINDOW", "")
    except Exception:
        return None


def notify(summary: str, body: str = "") -> None:
    """Fire a desktop notification. The tool is launched from a hotkey with no visible
    terminal, so this — not stderr — is the user-facing channel (kb/spec/error-taxonomy).
    Best-effort."""
    if whereis("notify-send"):
        try:
            subprocess.run(["notify-send", "-t", "3000", "-a", "talkhere", summary, body],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        except Exception:
            pass


def cue(kind: str) -> None:
    """Play a short audio blip so recording start/stop is unmistakable (U5). Best-effort;
    silently no-ops if no player or sample is available."""
    sounds = {
        "start": "/usr/share/sounds/freedesktop/stereo/dialog-information.oga",
        "stop": "/usr/share/sounds/freedesktop/stereo/message.oga",
        "done": "/usr/share/sounds/freedesktop/stereo/complete.oga",
    }
    path = sounds.get(kind)
    if path and whereis("paplay") and os.path.exists(path):
        try:
            subprocess.Popen(["paplay", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Configuration (precedence: flag > env > config.toml > default) — P11: never fatal
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """Read ~/.config/talkhere/config.toml if present. A malformed or absent file logs a
    warning and yields {} so defaults apply (P11) — config problems never abort talkhere."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        import tomllib  # stdlib >= 3.11
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except Exception as e:  # malformed TOML, unreadable, ancient python
        log(f"config: ignoring {CONFIG_FILE} ({e}); using defaults")
        notify("talkhere: bad config", "using defaults")
        return {}


def resolve(args, cfg: dict, key: str, env: str, default):
    """Resolve one setting by precedence. `key` is dotted into `cfg` (e.g. 'local.model')."""
    val = getattr(args, key.replace(".", "_"), None) if args else None
    if val is not None:
        return val
    if env and os.environ.get(env) is not None:
        return os.environ[env]
    node = cfg
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            node = None
            break
    return node if node is not None else default


def read_prompt() -> str | None:
    """The optional ~/.talkhere.prompt biases Whisper's spelling of jargon (T9)."""
    if PROMPT_FILE.exists():
        text = PROMPT_FILE.read_text(encoding="utf-8").strip()
        return text or None
    return None


# ---------------------------------------------------------------------------
# Recording (kb/external/audio-capture-pipewire.md)
# ---------------------------------------------------------------------------
def _recorder_cmd(wav: Path) -> list[str] | None:
    """Return the capture command for a 16 kHz mono WAV, preferring PipeWire then ALSA."""
    if whereis("pw-record"):
        return ["pw-record", "--rate", str(SAMPLE_RATE), "--channels", "1",
                "--format", "s16", str(wav)]
    if whereis("arecord"):
        return ["arecord", "-q", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1",
                "-t", "wav", str(wav)]
    return None


def start_recorder(wav: Path) -> subprocess.Popen | None:
    """Spawn a detached capture process writing `wav`. Detached (new session, stdio to
    /dev/null) so the caller can exit while recording continues (Step 2's START path)."""
    cmd = _recorder_cmd(wav)
    if cmd is None:
        return None
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def stop_recorder(proc: subprocess.Popen) -> None:
    """Stop a recorder cleanly. SIGINT first so pw-record/arecord finalise the WAV header
    (verified: an un-finalised header makes the file unreadable — T3/E11); escalate only if
    it ignores us."""
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=1.0)
        return
    except subprocess.TimeoutExpired:
        proc.terminate()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()


def _pid_alive(pid: int) -> bool:
    """True if a process with this pid currently exists (via /proc)."""
    return Path(f"/proc/{pid}").exists()


def stop_recorder_pid(pid: int) -> None:
    """Stop a recorder we did NOT spawn as our child (the toggle START process has exited;
    a later STOP process only has the pid). Same SIGINT-first clean-stop as stop_recorder,
    but polls /proc since we cannot waitpid() on a non-child (T3/E11)."""
    def gone() -> bool:
        return not _pid_alive(pid)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        if gone():
            return
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return
        for _ in range(20):                        # up to ~1 s for a clean WAV finalise
            if gone():
                return
            time.sleep(0.05)


def wav_duration_ms(wav: Path) -> int:
    """Duration of a WAV in milliseconds, or 0 if unreadable (treated as nothing-captured)."""
    try:
        with wave.open(str(wav)) as w:
            return int(1000 * w.getnframes() / w.getframerate())
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# STT backends (kb/architecture/decisions/0001) — Protocol + concrete + resolver
# ---------------------------------------------------------------------------
class Backend(Protocol):
    def transcribe(self, wav_path: str, lang: str) -> str: ...
    def available(self) -> bool: ...


class LocalBackend:
    """faster-whisper on the GPU (or CPU). Model is loaded lazily on first transcribe;
    kept on the instance so a future --serve warm mode can reuse it (Q5)."""

    def __init__(self, model: str, device: str, compute_type: str):
        # On Blackwell (sm_120) int8 crashes with cuBLAS NOT_SUPPORTED; float16 is required
        # (kb/external/faster-whisper-blackwell.md). Force it on cuda (E6).
        if device == "cuda" and compute_type.startswith("int8"):
            log(f"local: overriding compute_type {compute_type}->float16 on cuda (E6)")
            compute_type = "float16"
        self.model_name, self.device, self.compute_type = model, device, compute_type
        self._model = None

    def available(self) -> bool:
        """True if faster_whisper is importable. Cheap check that keeps the api-only install
        (no faster-whisper) from erroring at import (NF3)."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:
            return False

    @staticmethod
    def _preload_cuda_libs() -> None:
        """ctypes-preload the pip-installed cuDNN/cuBLAS (RTLD_GLOBAL) so CTranslate2's later
        dlopen-by-soname resolves them WITHOUT LD_LIBRARY_PATH being set before process start
        — essential when launched from an i3 hotkey. Load order matters: cuBLAS before cuDNN.
        Verified in kb/external/faster-whisper-blackwell.md."""
        import ctypes
        import glob
        import sysconfig
        purelib = sysconfig.get_paths()["purelib"]
        libdirs = sorted(glob.glob(os.path.join(purelib, "nvidia", "*", "lib")))
        for patterns in (["libcublas.so*", "libcublasLt.so*"],
                         ["libcudnn.so*"], ["libcudnn_*.so*"]):
            for d in libdirs:
                for pat in patterns:
                    for so in sorted(glob.glob(os.path.join(d, pat))):
                        try:
                            ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
                        except OSError as e:
                            log(f"local: preload skip {os.path.basename(so)}: {e}")

    @staticmethod
    def _free_vram_mb() -> int | None:
        """Free VRAM on GPU 0 in MiB, or None when unknowable (no nvidia-smi, no GPU).
        Cheap (~50 ms) and read-only — the price of a wasted 5 s model load is far higher."""
        if not whereis("nvidia-smi"):
            return None
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=memory.free",
                                "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5)
            return int(r.stdout.strip().splitlines()[0]) if r.returncode == 0 else None
        except Exception:
            return None

    def _vram_is_too_tight(self) -> bool:
        """True if the GPU has too little free memory to transcribe safely (E16).
        WHY: the GPU is shared (ollama, llama.cpp, games). When free VRAM is just under our
        footprint the model LOADS and then hits CUDA OOM mid-inference — the failure mode
        that silently lost dictations on 2026-07-23. Checking first turns that into a slow
        CPU run (text delivered) instead of a lost one."""
        try:                                       # a garbage env value must not be fatal (P11)
            need = int(os.environ.get("TALKHERE_MIN_VRAM_MB", MIN_FREE_VRAM_MB))
        except ValueError:
            need = MIN_FREE_VRAM_MB
        free = self._free_vram_mb()
        if free is None or free >= need:
            return False
        log(f"local: only {free} MiB VRAM free (< {need} needed); using cpu instead (E16)")
        notify("talkhere", f"GPU busy ({free} MiB free) — transcribing on CPU, slower…")
        return True

    def _load(self):
        """Construct (and cache) the WhisperModel, trying cuda then falling back to cpu (P10)."""
        from faster_whisper import WhisperModel
        if self.device == "cuda" and self._vram_is_too_tight():
            self.device, self.compute_type = "cpu", "int8"
        if self.device == "cuda":
            self._preload_cuda_libs()
        try:
            t0 = time.monotonic()
            m = WhisperModel(self.model_name, device=self.device,
                             compute_type=self.compute_type)
            log(f"local: loaded {self.model_name} on {self.device}/{self.compute_type} "
                f"in {time.monotonic()-t0:.2f}s")
            return m
        except Exception as e:
            if self.device == "cuda":  # cuda failed -> retry on cpu (P10/E5)
                log(f"local: cuda load failed ({e}); falling back to cpu/int8")
                self.device, self.compute_type = "cpu", "int8"
                m = WhisperModel(self.model_name, device="cpu", compute_type="int8")
                return m
            raise

    def transcribe(self, wav_path: str, lang: str) -> str:
        """Return the transcript ('' = no speech). `lang` 'auto' lets Whisper detect (P4).

        @invariant P10 — a cuda failure NEVER loses the utterance: the fallback ladder covers
        inference, not just model loading. A shared GPU can accept the model and then refuse
        the inference workspace (CUDA OOM), which used to escape as an unhandled exception."""
        try:
            return self._transcribe_once(wav_path, lang)
        except Exception as e:
            if self.device != "cuda":                  # already on cpu: nothing left to try
                raise
            log(f"local: cuda transcription failed ({e}); retrying on cpu/int8 (P10/E5)")
            notify("talkhere", "GPU failed — retrying on CPU, slower…")
            self.device, self.compute_type, self._model = "cpu", "int8", None
            return self._transcribe_once(wav_path, lang)

    def _transcribe_once(self, wav_path: str, lang: str) -> str:
        """One transcription attempt on the currently selected device (no fallback)."""
        if self._model is None:
            self._model = self._load()
        t0 = time.monotonic()
        segments, info = self._model.transcribe(
            wav_path,
            language=None if lang == "auto" else lang,   # P4
            initial_prompt=read_prompt(),                 # T9
            vad_filter=True,                              # trims silence (helps T2)
            condition_on_previous_text=False,             # curb silence hallucination (T2)
        )
        text = "".join(s.text for s in segments).strip()  # generator: work happens here
        log(f"local: transcribed in {time.monotonic()-t0:.2f}s lang={info.language} "
            f"len={len(text)}")
        return text


class ApiBackend:
    """OpenAI audio-transcription via curl + stdlib — no SDK, no faster-whisper (NF3).
    Key from env or the revisor keyring entry (kb/external/openai-transcription-api.md)."""

    def __init__(self, model: str):
        self.model = model

    def available(self) -> bool:
        return whereis("curl") and self._key() is not None

    @staticmethod
    def _key() -> str | None:
        """OpenAI key, never logged. Order: OPENAI_API_KEY env, else a GNOME keyring entry
        whose service/key default to talkhere/api-key and are overridable via
        TALKHERE_KEYRING_SERVICE / TALKHERE_KEYRING_KEY (e.g. point the service at another
        tool to reuse a key you already stored). Returns None if unavailable."""
        if os.environ.get("OPENAI_API_KEY"):
            return os.environ["OPENAI_API_KEY"]
        service = os.environ.get("TALKHERE_KEYRING_SERVICE", "talkhere")
        attr = os.environ.get("TALKHERE_KEYRING_KEY", "api-key")
        try:
            r = subprocess.run(["secret-tool", "lookup", "service", service, "key", attr],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip() or None if r.returncode == 0 else None
        except Exception:
            return None

    def transcribe(self, wav_path: str, lang: str) -> str:
        key = self._key()
        if not key:
            log("api: no key (env/keyring)"); return ""
        # The Authorization header carries the secret, so pass it via curl's stdin config
        # (-K -) instead of argv — keeps the key out of `ps` output. Non-secret form fields
        # stay in argv.
        cmd = ["curl", "-sS", "--max-time", "120", "-K", "-",
               "https://api.openai.com/v1/audio/transcriptions",
               "-F", f"model={self.model}", "-F", "response_format=text",
               "-F", f"file=@{wav_path}"]
        if lang != "auto":
            cmd += ["-F", f"language={lang}"]         # P4
        prompt = read_prompt()
        if prompt:
            cmd += ["-F", f"prompt={prompt}"]         # T9
        try:
            out = subprocess.run(cmd, input=f'header = "Authorization: Bearer {key}"\n',
                                 capture_output=True, text=True, timeout=125)
            if out.returncode != 0:
                log(f"api: curl rc={out.returncode} err={out.stderr[:200]!r}"); return ""
            return out.stdout.strip()
        except Exception as e:
            log(f"api: error {e}"); return ""


def resolve_backend(cfg: dict, args) -> Backend | None:
    """Build the fallback ladder and return the first available backend (P10).
    A forced --backend/env pin is honoured; otherwise local is tried, then api."""
    choice = resolve(args, cfg, "backend", "TALKHERE_BACKEND", "local")
    model = resolve(args, cfg, "local.model", "TALKHERE_MODEL", DEFAULT_MODEL)
    device = resolve(args, cfg, "local.device", "TALKHERE_DEVICE", "cuda")
    compute = resolve(args, cfg, "local.compute_type", "TALKHERE_COMPUTE", "float16")
    api_model = resolve(args, cfg, "api.model", "TALKHERE_API_MODEL", "whisper-1")

    local = LocalBackend(model, device, compute)
    api = ApiBackend(api_model)
    ladder = {"local": [local, api], "api": [api]}.get(choice, [local, api])
    for b in ladder:
        if b.available():
            log(f"backend: using {type(b).__name__} (requested {choice})")
            return b
        log(f"backend: {type(b).__name__} unavailable, trying next (P10)")
    return None


# ---------------------------------------------------------------------------
# Delivery sinks (kb/architecture/decisions/0003) — Protocol + concrete + resolver
# ---------------------------------------------------------------------------
class Sink(Protocol):
    def deliver(self, text: str) -> None: ...
    def available(self) -> bool: ...


class TypeSink:
    """Type text at the cursor via xdotool. Reads the text from stdin (`--file -`) so
    arbitrary UTF-8 (accents, quotes, `$`, newlines) is safe — no shell quoting, no argv
    limits (P3). --clearmodifiers drops a stuck Shift from the hotkey."""

    def __init__(self, key_delay_ms: int = 8):
        self.key_delay_ms = key_delay_ms

    def available(self) -> bool:
        return whereis("xdotool")

    def deliver(self, text: str) -> None:
        subprocess.run(["xdotool", "type", "--clearmodifiers",
                        "--delay", str(self.key_delay_ms), "--file", "-"],
                       input=text, text=True, check=True)


class PasteSink:
    """Set the clipboard then send a paste keystroke — Unicode-robust, but the chord differs
    per app (`paste_key`). Escape hatch when `type` misbehaves in some app."""

    def __init__(self, paste_key: str = "ctrl+v"):
        self.paste_key = paste_key

    def available(self) -> bool:
        return whereis("xclip") and whereis("xdotool")

    def deliver(self, text: str) -> None:
        subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=True)
        subprocess.run(["xdotool", "key", "--clearmodifiers", self.paste_key], check=True)


class ClipboardSink:
    """Put text on the clipboard; the user pastes it (or a clipboard manager such as KDE
    Klipper keeps it in history). Most robust, least magic — and the universal degradation
    target so recognised text is never lost (P7). Session-aware: wl-copy on Wayland, xclip on
    X11, so `--sink clipboard` works under both display servers (the only sink that does on
    Wayland, since type/paste need xdotool)."""

    def _cmd(self) -> list[str] | None:
        """The clipboard command for this session, or None if no tool is installed. Prefer the
        session's native tool; fall back to the other if only that one is present."""
        wl = ["wl-copy"] if whereis("wl-copy") else None
        xc = ["xclip", "-selection", "clipboard"] if whereis("xclip") else None
        order = (wl, xc) if _is_wayland() else (xc, wl)
        return next((c for c in order if c is not None), None)

    def available(self) -> bool:
        return self._cmd() is not None

    def deliver(self, text: str) -> None:
        cmd = self._cmd()
        if cmd is None:
            raise RuntimeError("no clipboard tool (install wl-clipboard on Wayland, xclip on X11)")
        subprocess.run(cmd, input=text, text=True, check=True)


def resolve_sink(cfg: dict, args) -> tuple[Sink | None, str]:
    """Return (sink, note). Honour the requested sink; if its tool is missing, degrade to
    clipboard so text survives (P7). Returns (None, reason) only if even clipboard is absent."""
    choice = resolve(args, cfg, "sink", "TALKHERE_SINK", "type")
    key_delay = int(resolve(args, cfg, "sink.type.key_delay_ms", None, 8))
    paste_key = resolve(args, cfg, "sink.paste.paste_key", None, "ctrl+v")
    candidates = {
        "type": TypeSink(key_delay), "paste": PasteSink(paste_key), "clipboard": ClipboardSink(),
    }
    sink = candidates.get(choice, TypeSink(key_delay))
    if sink.available():
        return sink, choice
    clip = ClipboardSink()
    if clip.available():
        log(f"sink: {choice} unavailable, degraded to clipboard (P7)")
        hint = ("typing needs X11 — text is on the clipboard, paste it (or grab it from Klipper)"
                if _is_wayland() else f"install the tool for the '{choice}' sink; paste manually")
        notify("talkhere: text on clipboard", hint)
        return clip, f"clipboard (degraded from {choice})"
    return None, "no sink available (install wl-clipboard on Wayland, or xclip on X11)"


@contextlib.contextmanager
def _focused_on(wid: str):
    """Hold the keyboard focus on `wid` for the duration of the block, and *keep* it there.

    Why the pointer dance: xdotool types via XTEST, which delivers each keystroke to whatever
    window is focused *at that instant*. With focus-follows-mouse (i3's default) a stray mouse
    motion mid-typing hands focus to another window and the rest of the transcript is scattered
    into it. Parking the pointer inside the target while typing removes that vector; we put it
    back afterwards. (`xdotool type --window` would avoid all this, but apps ignore those
    synthetic events — verified — so controlling focus is the only reliable route.)

    Raises RuntimeError if the target cannot be focused: callers must then NOT type (that would
    inject into the wrong window) and fall back to the clipboard instead.
    """
    before = _mouse_location()
    subprocess.run(["xdotool", "windowactivate", "--sync", wid],
                   check=True, timeout=5, capture_output=True)
    if _active_window() != wid:
        raise RuntimeError(f"could not focus target window {wid}")

    moved = False
    if before and before[2] != wid:                  # pointer sits over some other window
        try:
            subprocess.run(["xdotool", "mousemove", "--window", wid, "10", "10"],
                           timeout=2, capture_output=True)
            moved = True
        except Exception as e:                       # not fatal: typing still works
            log(f"focus: could not park pointer in {wid}: {e}")
    try:
        yield
    finally:
        if moved and before:                         # restore the pointer where the user left it
            subprocess.run(["xdotool", "mousemove", before[0], before[1]],
                           timeout=2, capture_output=True, check=False)


def deliver_focused(sink: Sink, text: str, target_wid: str | None) -> None:
    """Deliver `text`, first restoring focus to the window the utterance started in (P12).

    Only the focus-dependent sinks (type/paste) need this; the clipboard sink is
    focus-independent. Raises if the target window is gone or cannot be focused, so the caller
    falls back to the clipboard rather than typing somewhere unintended.
    """
    focus_dependent = isinstance(sink, (TypeSink, PasteSink))
    if not (focus_dependent and target_wid and whereis("xdotool")):
        sink.deliver(text)
        return
    if not _window_exists(target_wid):
        raise RuntimeError(f"target window {target_wid} no longer exists")
    with _focused_on(target_wid):
        sink.deliver(text)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def postprocess(text: str, trailing_space: bool) -> str:
    """Trim the whitespace Whisper adds; optionally append one space so consecutive
    dictations don't run together. Interior content is untouched (P6: talkhere transcribes,
    it does not edit)."""
    text = text.strip()
    if text and trailing_space:
        text += " "
    return text


def transcribe_and_deliver(wav: Path, cfg: dict, args, verbose: bool,
                           lang: str | None = None, target_wid: str | None = None) -> int:
    """Shared STOP-path tail: guard empties, transcribe via the ladder, deliver via the sink.
    Returns a process exit code. Used by --once and the toggle STOP path. `lang` overrides the
    resolved language, and `target_wid` is the window that was focused when the utterance
    STARTED — the transcript is delivered there, not wherever focus drifted to (P12)."""
    dur = wav_duration_ms(wav)
    if dur < MIN_MS:                                   # P5/T1: too short => nothing captured
        log(f"nothing captured (dur={dur}ms < {MIN_MS}ms)")
        notify("talkhere", "nothing captured")
        return 0

    backend = resolve_backend(cfg, args)
    if backend is None:                                # P9: no usable backend at all
        log("no backend available (local import failed and no API key)")
        notify("talkhere: no STT backend", "install faster-whisper or set an OpenAI key")
        return 1

    if lang is None:
        lang = resolve(args, cfg, "lang", "TALKHERE_LANG", "auto")
    cue("stop")
    notify("talkhere", "transcribing…")
    text = backend.transcribe(str(wav), lang)
    if not text.strip():                               # P5/E4: no speech recognised
        log("empty transcription")
        notify("talkhere", "no speech recognised")
        return 0

    trailing = str(resolve(args, cfg, "trailing_space", "TALKHERE_TRAILING_SPACE", "1")) not in \
        ("0", "false", "False", "no")
    text = postprocess(text, trailing)
    if verbose:
        print(text)

    sink, note = resolve_sink(cfg, args)
    if sink is None:
        log("no sink available"); notify("talkhere: cannot deliver text", note)
        return 1
    try:
        # Restore focus to the window the utterance started in, and hold it there while typing
        # (P12). If that window is gone / unfocusable this RAISES rather than typing into
        # whatever happens to be focused now — wrong-window injection is the cardinal sin.
        deliver_focused(sink, text, target_wid)
    except Exception as e:                             # target gone, or a sink tool failed
        log(f"sink {note} failed ({e}); last resort clipboard")
        try:
            ClipboardSink().deliver(text)
            note = "clipboard (could not reach the target window)"
            notify("talkhere: text on clipboard",
                   "the window you started dictating in is gone — paste it")
        except Exception:
            notify("talkhere: delivery failed", str(e)); return 1
    cue("done")
    preview = (text[:40] + "…") if len(text) > 40 else text
    log(f"delivered via {note}: {preview!r}")
    notify("talkhere ✓", preview.strip())
    return 0


def keep_failed_wav(wav: Path) -> Path | None:
    """Move `wav` into ~/.talkhere/failed/ and prune to the FAILED_KEEP most recent.
    Returns the new path (None if the audio was already gone).

    @invariant P13 — audio outlives a failed transcription. The runtime dir lives under
    /run, which the session wipes; a two-minute dictation must not evaporate because the
    GPU was busy. Retry it later with `talkhere --retry-last`."""
    if not wav.exists():
        return None
    try:
        FAILED_DIR.mkdir(parents=True, exist_ok=True)
        dest = FAILED_DIR / wav.name
        shutil.move(str(wav), str(dest))               # /run -> $HOME: a copy, not a rename
        keep = sorted(FAILED_DIR.glob("*.wav"), key=lambda p: p.stat().st_mtime)[:-FAILED_KEEP]
        for old in keep:                               # bounded: never a silent disk hog
            old.unlink(missing_ok=True)
        log(f"audio preserved at {dest} (retry with: talkhere --retry-last)")
        return dest
    except Exception as e:                             # preserving is best-effort, never fatal
        log(f"could not preserve {wav}: {e}")
        return None


def transcribe_or_keep(wav: Path, cfg: dict, args, verbose: bool,
                       lang: str | None = None, target_wid: str | None = None) -> int:
    """`transcribe_and_deliver` with a safety net: on ANY failure the audio is preserved and
    the user is told, instead of a traceback vanishing into a hotkey's absent terminal
    (P13/E15). On success the wav is removed unless TALKHERE_KEEP_WAV."""
    try:
        rc = transcribe_and_deliver(wav, cfg, args, verbose, lang=lang, target_wid=target_wid)
    except Exception as e:
        log(f"transcription failed: {type(e).__name__}: {e}\n{traceback.format_exc().rstrip()}")
        kept = keep_failed_wav(wav)
        notify("talkhere: transcription failed",
               "audio kept — run: talkhere --retry-last" if kept else f"{type(e).__name__}: {e}")
        return 1
    if rc != 0:                                        # delivery/backend gave up: keep the audio
        keep_failed_wav(wav)
    elif os.environ.get("TALKHERE_KEEP_WAV", "0") == "0":
        wav.unlink(missing_ok=True)
    return rc


def latest_failed_wav() -> Path | None:
    """The most recent preserved recording, or None."""
    if not FAILED_DIR.exists():
        return None
    wavs = sorted(FAILED_DIR.glob("*.wav"), key=lambda p: p.stat().st_mtime)
    return wavs[-1] if wavs else None


def cmd_transcribe_file(wav: Path, cfg: dict, args, verbose: bool, drop_on_success: bool) -> int:
    """`--file WAV` / `--retry-last`: transcribe an existing recording and deliver it.

    The target window is the one focused NOW (P12 remembers the START window, but here the
    user is explicitly asking at this moment, so "here" is what they mean). `drop_on_success`
    removes a preserved wav once its text has landed, so --retry-last doesn't replay it."""
    if not wav.exists():
        notify("talkhere", "no recording to retry"); log(f"retry: {wav} not found")
        return 1
    log(f"RETRY {wav}")
    target = _target_window(_active_window(), cfg, args)
    try:
        rc = transcribe_and_deliver(wav, cfg, args, verbose, target_wid=target)
    except Exception as e:                             # keep the audio: the retry can be retried
        log(f"retry failed: {type(e).__name__}: {e}\n{traceback.format_exc().rstrip()}")
        notify("talkhere: transcription failed", f"{type(e).__name__} — audio kept at {wav}")
        return 1
    if rc == 0 and drop_on_success:
        wav.unlink(missing_ok=True)
    return rc


def cmd_once(seconds: float, cfg: dict, args, verbose: bool) -> int:
    """`--once N`: record N seconds, then transcribe+deliver. The Step-1 vertical slice —
    no toggle/state, just proves record -> STT -> sink end to end."""
    if _recorder_cmd(Path("/x")) is None:              # P9/E2: hard precondition
        notify("talkhere: no recorder", "install pw-record or arecord"); return 1
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    wav = RUNTIME_DIR / f"once-{int(time.time())}.wav"
    log(f"--once {seconds}s -> {wav}")
    cue("start")
    notify("talkhere", f"● recording {seconds:g}s")
    window = _active_window()                          # deliver back here, not wherever focus drifts (P12)
    proc = start_recorder(wav)
    if proc is None:
        notify("talkhere: no recorder", "install pw-record or arecord"); return 1
    try:
        time.sleep(seconds)
    finally:
        stop_recorder(proc)
    return transcribe_or_keep(wav, cfg, args, verbose,
                              target_wid=_target_window(window, cfg, args))


# ---------------------------------------------------------------------------
# Toggle state machine (kb/spec/algorithms.md, kb/architecture/decisions/0002)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _lock():
    """Serialise the read-decide-write of the state file so two near-simultaneous hotkey
    presses can't both START a recorder (P8). Held only around the decision, never during
    transcription — so a press mid-transcribe starts the next utterance rather than blocking."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    f = open(LOCK_FILE, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def read_state() -> dict | None:
    """Return the recording state, or None if idle. Self-heals a STALE state file whose
    recorder pid is dead (crash/reboot) by clearing it and reporting idle (E9/T4)."""
    if not STATE_FILE.exists():
        return None
    try:
        st = json.loads(STATE_FILE.read_text())
    except Exception:                                  # corrupt state => treat as idle
        clear_state()
        return None
    pid = st.get("pid")
    if not pid or not _pid_alive(int(pid)):
        log("state: recovered stale recording.json (recorder pid dead) (E9)")
        clear_state()
        return None
    return st


def write_state(st: dict) -> None:
    STATE_FILE.write_text(json.dumps(st))


def clear_state() -> None:
    STATE_FILE.unlink(missing_ok=True)


def _start(cfg: dict, args) -> int:
    """START branch: spawn a detached recorder, record the pid+wav in the state file, cue,
    and return so this process can exit while recording continues. Assumes the lock is held."""
    if _recorder_cmd(Path("/x")) is None:              # P9/E2 hard precondition
        notify("talkhere: no recorder", "install pw-record or arecord")
        return 1
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    wav = RUNTIME_DIR / f"utterance-{int(time.time())}.wav"
    proc = start_recorder(wav)
    if proc is None:
        notify("talkhere: no recorder", "install pw-record or arecord")
        return 1
    lang = resolve(args, cfg, "lang", "TALKHERE_LANG", "auto")
    # Remember WHERE the user began dictating. Focus will very likely have moved by the time
    # they stop (they read, they switch windows while speaking), and the transcript must land
    # where they started, not wherever the cursor ended up (P12).
    window = _active_window()
    write_state({"pid": proc.pid, "wav": str(wav), "started": time.time(), "lang": lang,
                 "window": window})
    log(f"START recorder pid={proc.pid} wav={wav} lang={lang} window={window}")
    cue("start")
    notify("talkhere", "● recording — press again to stop")
    return 0


def _target_window(st_window: str | None, cfg: dict, args) -> str | None:
    """Which window should receive the text: the one focused at START (default), or whatever
    is focused now (`TALKHERE_TARGET_WINDOW=current`, the pre-P12 behaviour)."""
    mode = resolve(args, cfg, "target_window", "TALKHERE_TARGET_WINDOW", "start")
    return st_window if mode == "start" else None


def _stop(st: dict, cfg: dict, args, verbose: bool) -> int:
    """STOP branch: stop the recorder cleanly, then transcribe+deliver its wav. Assumes the
    state has already been cleared under the lock, so a new press can START concurrently."""
    wav = Path(st["wav"])
    stop_recorder_pid(int(st["pid"]))
    log(f"STOP recorder pid={st['pid']} wav={wav}")
    return transcribe_or_keep(wav, cfg, args, verbose, lang=st.get("lang"),
                              target_wid=_target_window(st.get("window"), cfg, args))


def cmd_toggle(cfg: dict, args, verbose: bool) -> int:
    """No-arg invocation: START if idle, else STOP. The decision is made under the lock;
    transcription (slow) happens after the lock is released."""
    with _lock():
        st = read_state()
        if st is None:
            return _start(cfg, args)
        clear_state()                                  # we own this utterance now
    return _stop(st, cfg, args, verbose)


def cmd_cancel() -> int:
    """Abort an in-progress recording: kill the recorder, drop the wav, inject nothing."""
    with _lock():
        st = read_state()
        if st is None:
            notify("talkhere", "nothing to cancel")
            return 0
        clear_state()
    stop_recorder_pid(int(st["pid"]))
    Path(st["wav"]).unlink(missing_ok=True)
    log("CANCEL: recording discarded")
    notify("talkhere", "recording cancelled")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="talkhere", description="Talk-to-type: speak, and the text is typed at the cursor.")
    p.add_argument("--once", type=float, metavar="SECS",
                   help="record SECS seconds then transcribe+inject (no toggle; scripting/test)")
    p.add_argument("--stop", action="store_true",
                   help="force stop+transcribe an in-progress recording")
    p.add_argument("--cancel", action="store_true",
                   help="abort an in-progress recording; inject nothing")
    p.add_argument("--status", action="store_true",
                   help="print idle|recording; exit 0 if idle else 1 (for i3blocks)")
    p.add_argument("--retry-last", action="store_true",
                   help="re-transcribe the last recording whose transcription failed (P13)")
    p.add_argument("--file", metavar="WAV",
                   help="transcribe an existing WAV and deliver it (no recording)")
    p.add_argument("--lang", choices=["auto", "fr", "en"], help="force language for this run (P4)")
    p.add_argument("--backend", choices=["local", "api"], help="override STT backend")
    p.add_argument("--sink", choices=["type", "paste", "clipboard"], help="override delivery")
    p.add_argument("-v", "--verbose", action="store_true", help="also echo the transcript to stdout")
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point with the mandatory safety net (kb/conventions/code-and-testing.md):
    talkhere runs from a hotkey with no terminal, so an unhandled exception would be an
    invisible death — no log line, no notification, and (before P13) a lost recording.
    Everything that escapes `_dispatch` is logged with its traceback and notified (E15)."""
    try:
        return _dispatch(argv)
    except SystemExit:                                 # argparse --help/usage: not an error
        raise
    except KeyboardInterrupt:
        log("interrupted (SIGINT)")
        return 130
    except Exception as e:
        log(f"FATAL {type(e).__name__}: {e}\n{traceback.format_exc().rstrip()}")
        notify("talkhere: unexpected error", f"{type(e).__name__}: {e}"[:150])
        return 1


def _dispatch(argv: list[str] | None) -> int:
    """Parse the flags and run the selected command. Raises freely — main() is the net."""
    args = build_parser().parse_args(argv)
    cfg = load_config()

    if args.status:
        # read_state() self-heals a stale lock; kept fast and GPU-free for i3blocks polling.
        recording = read_state() is not None
        print("recording" if recording else "idle")
        return 1 if recording else 0

    if args.cancel:
        return cmd_cancel()

    if args.retry_last or args.file:                   # recover a failed transcription (P13)
        wav = Path(args.file) if args.file else latest_failed_wav()
        if wav is None:
            notify("talkhere", "no failed recording to retry")
            log("retry-last: nothing preserved")
            return 0
        return cmd_transcribe_file(wav, cfg, args, args.verbose,
                                   drop_on_success=not args.file)

    if args.once is not None:
        return cmd_once(args.once, cfg, args, args.verbose)

    if args.stop:                                      # force STOP (a distinct binding, if wanted)
        with _lock():
            st = read_state()
            if st is None:
                notify("talkhere", "not recording")
                return 0
            clear_state()
        return _stop(st, cfg, args, args.verbose)

    return cmd_toggle(cfg, args, args.verbose)         # no args => toggle


if __name__ == "__main__":
    sys.exit(main())                                   # main() already nets every exception
