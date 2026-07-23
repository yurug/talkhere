"""Tests for talkhere. Each test name starts with the property/edge id it defends
(kb/properties/) so coverage is greppable against the KB. The bulk run with fakes — no
GPU, mic, or X server needed; the one GPU integration test self-skips when unavailable.
"""
import types
import wave
import pytest

import talkhere


# ---------------------------------------------------------------------------
# Fakes / helpers (DI: the orchestrator depends only on the Backend/Sink Protocols)
# ---------------------------------------------------------------------------
class FakeBackend:
    def __init__(self, text):
        self.text, self.calls = text, []

    def available(self):
        return True

    def transcribe(self, wav_path, lang):
        self.calls.append((wav_path, lang))
        return self.text


class FakeSink:
    def __init__(self):
        self.delivered = []

    def available(self):
        return True

    def deliver(self, text):
        self.delivered.append(text)


def make_wav(path, ms):
    """Write a silent mono 16 kHz WAV of `ms` milliseconds."""
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * ms / 1000))


def ns(**kw):
    """An argparse-like namespace with all CLI attrs defaulted to None/False."""
    base = dict(once=None, status=False, lang=None, backend=None, sink=None, verbose=False,
                stop=False, cancel=False, retry_last=False, file=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _mute_feedback(monkeypatch, tmp_path):
    """Feedback (notify/sound) is best-effort UI; silence it so tests stay hermetic. The log
    is redirected too — a test run must never write into the user's real ~/.talkhere.log."""
    monkeypatch.setattr(talkhere, "notify", lambda *a, **k: None)
    monkeypatch.setattr(talkhere, "cue", lambda *a, **k: None)
    monkeypatch.setattr(talkhere, "LOG_FILE", tmp_path / "talkhere.log")


# ---------------------------------------------------------------------------
# P6 — fidelity: talkhere transcribes, it does not edit
# ---------------------------------------------------------------------------
def test_P6_postprocess_trims_and_adds_single_trailing_space():
    assert talkhere.postprocess("  hello  ", trailing_space=True) == "hello "


def test_P6_postprocess_no_trailing_when_disabled():
    assert talkhere.postprocess("  hello  ", trailing_space=False) == "hello"


def test_P6_postprocess_preserves_interior_bytes():
    # Interior spacing, accents and punctuation must survive untouched.
    src = "Café,  déçu — ça va ? 🙂"
    assert talkhere.postprocess(src + "  ", trailing_space=False) == src


def test_P6_delivered_text_is_what_backend_returned(monkeypatch, tmp_path):
    wav = tmp_path / "u.wav"
    make_wav(wav, 1000)
    sink = FakeSink()
    monkeypatch.setattr(talkhere, "resolve_backend", lambda cfg, args: FakeBackend("Hello world"))
    monkeypatch.setattr(talkhere, "resolve_sink", lambda cfg, args: (sink, "fake"))
    rc = talkhere.transcribe_and_deliver(wav, {}, ns(), verbose=False)
    assert rc == 0
    assert sink.delivered == ["Hello world "]   # +1 trailing space by default


# ---------------------------------------------------------------------------
# P5 — never inject on empty / nothing captured
# ---------------------------------------------------------------------------
def test_P5_empty_transcription_never_delivers(monkeypatch, tmp_path):
    wav = tmp_path / "u.wav"
    make_wav(wav, 1000)
    sink = FakeSink()
    monkeypatch.setattr(talkhere, "resolve_backend", lambda cfg, args: FakeBackend("   "))
    monkeypatch.setattr(talkhere, "resolve_sink", lambda cfg, args: (sink, "fake"))
    rc = talkhere.transcribe_and_deliver(wav, {}, ns(), verbose=False)
    assert rc == 0
    assert sink.delivered == []                 # nothing injected


def test_P5_too_short_wav_is_nothing_captured(monkeypatch, tmp_path):
    wav = tmp_path / "u.wav"
    make_wav(wav, 100)                            # < MIN_MS
    def boom(*a, **k):
        raise AssertionError("backend must not be built for a too-short clip")
    monkeypatch.setattr(talkhere, "resolve_backend", boom)
    rc = talkhere.transcribe_and_deliver(wav, {}, ns(), verbose=False)
    assert rc == 0


# ---------------------------------------------------------------------------
# P4 — language control threads flag -> backend
# ---------------------------------------------------------------------------
def test_P4_forced_language_reaches_backend(monkeypatch, tmp_path):
    wav = tmp_path / "u.wav"
    make_wav(wav, 1000)
    backend = FakeBackend("bonjour")
    monkeypatch.setattr(talkhere, "resolve_backend", lambda cfg, args: backend)
    monkeypatch.setattr(talkhere, "resolve_sink", lambda cfg, args: (FakeSink(), "fake"))
    talkhere.transcribe_and_deliver(wav, {}, ns(lang="fr"), verbose=False)
    assert backend.calls and backend.calls[0][1] == "fr"


# ---------------------------------------------------------------------------
# P7 — sink degradation preserves text
# ---------------------------------------------------------------------------
def test_P7_type_sink_degrades_to_clipboard_when_xdotool_absent(monkeypatch):
    present = {"xclip"}                            # xdotool missing, xclip present
    monkeypatch.setattr(talkhere, "whereis", lambda c: c in present)
    sink, note = talkhere.resolve_sink({}, ns(sink="type"))
    assert isinstance(sink, talkhere.ClipboardSink)
    assert "clipboard" in note


def test_P7_no_sink_when_even_xclip_missing(monkeypatch):
    monkeypatch.setattr(talkhere, "whereis", lambda c: False)
    sink, note = talkhere.resolve_sink({}, ns(sink="type"))
    assert sink is None


# --- Wayland: the clipboard sink is session-aware (wl-copy) so it works on KDE/Klipper ---
def _capture_run(monkeypatch):
    calls = []
    monkeypatch.setattr(talkhere.subprocess, "run",
                        lambda cmd, **k: calls.append((cmd, k.get("input")))
                        or types.SimpleNamespace(returncode=0))
    return calls


def test_clipboard_sink_uses_wl_copy_on_wayland(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(talkhere, "whereis", lambda c: c in {"wl-copy", "xclip"})
    calls = _capture_run(monkeypatch)
    talkhere.ClipboardSink().deliver("bonjour")
    assert calls[0][0] == ["wl-copy"] and calls[0][1] == "bonjour"


def test_clipboard_sink_uses_xclip_on_x11(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(talkhere, "whereis", lambda c: c in {"wl-copy", "xclip"})
    calls = _capture_run(monkeypatch)
    talkhere.ClipboardSink().deliver("hello")
    assert calls[0][0][0] == "xclip" and calls[0][1] == "hello"


def test_P7_wayland_type_degrades_to_wl_copy_clipboard(monkeypatch):
    # On Wayland xdotool is absent → the `type` default degrades to the clipboard, backed by
    # wl-copy (the KDE/Klipper use case). Text is never lost.
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(talkhere, "whereis", lambda c: c == "wl-copy")   # no xdotool/xclip
    monkeypatch.setattr(talkhere, "notify", lambda *a, **k: None)
    sink, note = talkhere.resolve_sink({}, ns(sink="type"))
    assert isinstance(sink, talkhere.ClipboardSink) and sink.available()
    assert "clipboard" in note


# ---------------------------------------------------------------------------
# P3 — accent path: TypeSink must feed text via stdin (--file -), never argv
# ---------------------------------------------------------------------------
def test_P3_type_sink_uses_file_stdin_for_unicode(monkeypatch):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"], captured["input"] = cmd, kw.get("input")
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(talkhere.subprocess, "run", fake_run)
    talkhere.TypeSink(key_delay_ms=8).deliver("Café — déçu 🙂")
    assert captured["cmd"][:2] == ["xdotool", "type"]
    assert "--file" in captured["cmd"] and captured["cmd"][-1] == "-"
    assert captured["input"] == "Café — déçu 🙂"   # exact bytes, no shell quoting


# ---------------------------------------------------------------------------
# Config precedence: flag > env > cfg > default
# ---------------------------------------------------------------------------
def test_resolve_precedence(monkeypatch):
    monkeypatch.delenv("TALKHERE_BACKEND", raising=False)
    assert talkhere.resolve(ns(), {}, "backend", "TALKHERE_BACKEND", "local") == "local"
    assert talkhere.resolve(ns(), {"backend": "api"}, "backend", "TALKHERE_BACKEND", "local") == "api"
    monkeypatch.setenv("TALKHERE_BACKEND", "api")
    assert talkhere.resolve(ns(), {}, "backend", "TALKHERE_BACKEND", "local") == "api"
    assert talkhere.resolve(ns(backend="local"), {"backend": "api"},
                            "backend", "TALKHERE_BACKEND", "local") == "local"


def test_resolve_dotted_key_into_config():
    cfg = {"local": {"model": "medium"}}
    assert talkhere.resolve(ns(), cfg, "local.model", "TALKHERE_MODEL", "large-v3-turbo") == "medium"


# ---------------------------------------------------------------------------
# P11 — config never fatal
# ---------------------------------------------------------------------------
def test_P11_bad_config_yields_defaults(monkeypatch, tmp_path):
    bad = tmp_path / "config.toml"
    bad.write_text("this is = = not valid toml [[[")
    monkeypatch.setattr(talkhere, "CONFIG_FILE", bad)
    assert talkhere.load_config() == {}           # no raise


# ---------------------------------------------------------------------------
# Toggle state machine (P1 toggle, P8 single-recorder, E9 stale recovery)
# ---------------------------------------------------------------------------
@pytest.fixture
def runtime(tmp_path, monkeypatch):
    """Redirect the runtime dir / state / lock files into a temp dir for hermetic tests."""
    monkeypatch.setattr(talkhere, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(talkhere, "STATE_FILE", tmp_path / "recording.json")
    monkeypatch.setattr(talkhere, "LOCK_FILE", tmp_path / "talkhere.lock")
    return tmp_path


def _stub_recorder(monkeypatch, alive=True):
    """Replace the real recorder/pid/stop/transcribe with observable stubs. Returns
    (start_calls, stops, delivered)."""
    start_calls, stops, delivered = [], [], []

    class FakeProc:
        pid = 4242

    def fake_start(wav):
        start_calls.append(str(wav))
        return FakeProc()

    monkeypatch.setattr(talkhere, "_recorder_cmd", lambda w: ["true"])
    monkeypatch.setattr(talkhere, "start_recorder", fake_start)
    monkeypatch.setattr(talkhere, "_pid_alive", lambda pid: alive)
    monkeypatch.setattr(talkhere, "stop_recorder_pid", lambda pid: stops.append(pid))
    monkeypatch.setattr(talkhere, "transcribe_and_deliver",
                        lambda wav, cfg, args, verbose, lang=None, target_wid=None:
                        delivered.append((str(wav), lang, target_wid)) or 0)
    return start_calls, stops, delivered


def test_P1_toggle_starts_then_stops(runtime, monkeypatch):
    start_calls, stops, delivered = _stub_recorder(monkeypatch)
    assert talkhere.cmd_toggle({}, ns(), verbose=False) == 0     # START
    st = talkhere.read_state()
    assert st is not None and st["pid"] == 4242                  # recording
    assert talkhere.cmd_toggle({}, ns(), verbose=False) == 0     # STOP
    assert talkhere.read_state() is None                        # idle again (P1)
    assert stops == [4242] and delivered                        # recorder stopped, wav delivered
    assert delivered[0][1] == "auto"                            # lang threaded from state (P4)


def test_P8_second_toggle_does_not_start_a_second_recorder(runtime, monkeypatch):
    start_calls, stops, delivered = _stub_recorder(monkeypatch)
    talkhere.cmd_toggle({}, ns(), verbose=False)                 # START
    talkhere.cmd_toggle({}, ns(), verbose=False)                 # STOP, must NOT start again
    assert len(start_calls) == 1                                 # exactly one recorder (P8)


def test_E9_stale_state_self_heals(runtime, monkeypatch):
    monkeypatch.setattr(talkhere, "_pid_alive", lambda pid: False)   # recorder pid is dead
    talkhere.write_state({"pid": 999999, "wav": "/x", "started": 0, "lang": "auto"})
    assert talkhere.read_state() is None                        # reported idle
    assert not talkhere.STATE_FILE.exists()                     # and the stale file is cleaned


def test_cancel_stops_recorder_and_injects_nothing(runtime, monkeypatch):
    start_calls, stops, delivered = _stub_recorder(monkeypatch)
    talkhere.cmd_toggle({}, ns(), verbose=False)                 # START
    assert talkhere.cmd_cancel() == 0
    assert talkhere.read_state() is None                        # idle
    assert stops == [4242] and delivered == []                  # stopped, nothing delivered (P5)


# ---------------------------------------------------------------------------
# P12 — the transcript lands in the window where dictation STARTED, and stays there
# ---------------------------------------------------------------------------
def test_P12_start_remembers_the_focused_window(runtime, monkeypatch):
    _stub_recorder(monkeypatch)
    monkeypatch.setattr(talkhere, "_active_window", lambda: "12345")
    talkhere.cmd_toggle({}, ns(), verbose=False)                 # START
    assert talkhere.read_state()["window"] == "12345"


def test_P12_delivery_refocuses_target_and_guards_the_pointer(monkeypatch):
    monkeypatch.setattr(talkhere, "whereis", lambda c: True)
    monkeypatch.setattr(talkhere, "_window_exists", lambda w: True)
    monkeypatch.setattr(talkhere, "_active_window", lambda: "42")
    monkeypatch.setattr(talkhere, "_mouse_location", lambda: ("100", "200", "99"))  # pointer elsewhere
    calls = []
    monkeypatch.setattr(talkhere.subprocess, "run",
                        lambda cmd, **k: calls.append((cmd, k.get("input")))
                        or types.SimpleNamespace(returncode=0))
    talkhere.deliver_focused(talkhere.TypeSink(8), "salut", "42")
    flat = [" ".join(c) for c, _ in calls]
    assert any("windowactivate --sync 42" in f for f in flat)    # focus restored to the target
    assert any("mousemove --window 42" in f for f in flat)       # pointer parked → no focus steal
    assert any("xdotool type" in f for f in flat)
    assert any(inp == "salut" for _, inp in calls)               # text typed via stdin
    assert flat[-1] == "xdotool mousemove 100 200"               # pointer put back afterwards


def test_P12_never_types_into_the_wrong_window_when_target_is_gone(monkeypatch, tmp_path):
    """The cardinal sin: if the window we started in is gone, DON'T type into whatever is
    focused now — preserve the text on the clipboard instead."""
    wav = tmp_path / "u.wav"
    make_wav(wav, 1000)
    typed = []

    class RecordingTypeSink(talkhere.TypeSink):
        def deliver(self, text):
            typed.append(text)                                   # must never happen

    clipped = []
    monkeypatch.setattr(talkhere, "resolve_backend", lambda cfg, args: FakeBackend("bonjour"))
    monkeypatch.setattr(talkhere, "resolve_sink", lambda cfg, args: (RecordingTypeSink(8), "type"))
    monkeypatch.setattr(talkhere, "whereis", lambda c: True)
    monkeypatch.setattr(talkhere, "_window_exists", lambda w: False)     # target window closed
    monkeypatch.setattr(talkhere.ClipboardSink, "deliver",
                        lambda self, text: clipped.append(text))
    rc = talkhere.transcribe_and_deliver(wav, {}, ns(), verbose=False, target_wid="999")
    assert rc == 0
    assert typed == []                                           # nothing typed anywhere
    assert clipped == ["bonjour "]                               # text preserved (P7)


def test_P12_clipboard_sink_needs_no_focus_dance(monkeypatch):
    checked, got = [], []
    monkeypatch.setattr(talkhere, "whereis", lambda c: True)
    monkeypatch.setattr(talkhere, "_window_exists", lambda w: checked.append(w) or True)
    monkeypatch.setattr(talkhere.ClipboardSink, "deliver", lambda self, t: got.append(t))
    talkhere.deliver_focused(talkhere.ClipboardSink(), "x", "42")
    assert got == ["x"] and checked == []                        # focus-independent sink


def test_P12_target_window_current_mode_restores_old_behaviour(monkeypatch):
    monkeypatch.setenv("TALKHERE_TARGET_WINDOW", "current")
    assert talkhere._target_window("42", {}, ns()) is None       # type wherever focus is now
    monkeypatch.setenv("TALKHERE_TARGET_WINDOW", "start")
    assert talkhere._target_window("42", {}, ns()) == "42"


# ---------------------------------------------------------------------------
# Step 3: config, prompt bias, backend fallback ladder, api key, paste sink
# ---------------------------------------------------------------------------
def test_config_toml_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("TALKHERE_SINK", raising=False)
    monkeypatch.delenv("TALKHERE_MODEL", raising=False)
    cfg = tmp_path / "config.toml"
    cfg.write_text('sink = "clipboard"\ntrailing_space = false\n[local]\nmodel = "medium"\n')
    monkeypatch.setattr(talkhere, "CONFIG_FILE", cfg)
    loaded = talkhere.load_config()
    assert loaded["sink"] == "clipboard"
    assert talkhere.resolve(ns(), loaded, "sink", "TALKHERE_SINK", "type") == "clipboard"
    assert talkhere.resolve(ns(), loaded, "local.model", "TALKHERE_MODEL", "large-v3-turbo") == "medium"


def test_T9_prompt_bias(tmp_path, monkeypatch):
    pf = tmp_path / ".talkhere.prompt"
    monkeypatch.setattr(talkhere, "PROMPT_FILE", pf)
    assert talkhere.read_prompt() is None                       # absent → no bias
    pf.write_text("Nomadic Labs, OCaml, Tezos\n")
    assert talkhere.read_prompt() == "Nomadic Labs, OCaml, Tezos"


def test_P10_cuda_failure_falls_back_to_cpu(monkeypatch):
    fw = pytest.importorskip("faster_whisper")
    calls = []

    def fake_model(name, device, compute_type):
        calls.append((device, compute_type))
        if device == "cuda":
            raise RuntimeError("simulated cuda init failure")
        return object()

    monkeypatch.setattr(fw, "WhisperModel", fake_model)
    monkeypatch.setattr(talkhere.LocalBackend, "_preload_cuda_libs", staticmethod(lambda: None))
    monkeypatch.setattr(talkhere.LocalBackend, "_free_vram_mb", staticmethod(lambda: 99999))
    monkeypatch.setattr(talkhere, "log", lambda *a: None)      # ample VRAM: exercise the LOAD path
    be = talkhere.LocalBackend("m", "cuda", "float16")
    be._load()
    assert be.device == "cpu"                                   # cascaded to cpu (P10/E5)
    assert calls == [("cuda", "float16"), ("cpu", "int8")]


def test_P10_cuda_inference_failure_falls_back_to_cpu(monkeypatch):
    """The 2026-07-23 regression: a shared GPU accepts the model, then OOMs during the
    transcription. That must downshift to cpu, not escape as an exception."""
    fw = pytest.importorskip("faster_whisper")
    devices = []

    class FakeModel:
        def __init__(self, device):
            self.device = device

        def transcribe(self, *a, **kw):
            if self.device == "cuda":
                raise RuntimeError("CUDA failed with error out of memory")
            return ([types.SimpleNamespace(text="bonjour")],
                    types.SimpleNamespace(language="fr"))

    monkeypatch.setattr(fw, "WhisperModel",
                        lambda name, device, compute_type: devices.append(device) or
                        FakeModel(device))
    monkeypatch.setattr(talkhere.LocalBackend, "_preload_cuda_libs", staticmethod(lambda: None))
    monkeypatch.setattr(talkhere.LocalBackend, "_free_vram_mb", staticmethod(lambda: 99999))
    monkeypatch.setattr(talkhere, "log", lambda *a: None)
    be = talkhere.LocalBackend("m", "cuda", "float16")
    assert be.transcribe("x.wav", "auto") == "bonjour"           # text delivered, not lost
    assert devices == ["cuda", "cpu"] and be.device == "cpu"     # downshifted (P10/E5)


def test_E16_tight_vram_skips_cuda_entirely(monkeypatch):
    """Below the VRAM floor we don't even try cuda: loading would succeed and inference
    would then die — the failure mode that lost dictations."""
    fw = pytest.importorskip("faster_whisper")
    devices = []
    monkeypatch.setattr(fw, "WhisperModel",
                        lambda name, device, compute_type: devices.append(device) or object())
    monkeypatch.setattr(talkhere.LocalBackend, "_free_vram_mb", staticmethod(lambda: 800))
    monkeypatch.setattr(talkhere, "log", lambda *a: None)
    be = talkhere.LocalBackend("m", "cuda", "float16")
    be._load()
    assert devices == ["cpu"] and be.compute_type == "int8"      # never touched cuda (E16)


def test_E16_ample_vram_uses_cuda(monkeypatch):
    fw = pytest.importorskip("faster_whisper")
    devices = []
    monkeypatch.setattr(fw, "WhisperModel",
                        lambda name, device, compute_type: devices.append(device) or object())
    monkeypatch.setattr(talkhere.LocalBackend, "_preload_cuda_libs", staticmethod(lambda: None))
    monkeypatch.setattr(talkhere.LocalBackend, "_free_vram_mb", staticmethod(lambda: 8000))
    monkeypatch.setattr(talkhere, "log", lambda *a: None)
    talkhere.LocalBackend("m", "cuda", "float16")._load()
    assert devices == ["cuda"]


# ---------------------------------------------------------------------------
# P13 — no failure is silent, and the audio outlives it
# ---------------------------------------------------------------------------
def _failed_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(talkhere, "FAILED_DIR", tmp_path / "failed")
    return tmp_path / "failed"


def test_P13_failed_transcription_preserves_the_audio(monkeypatch, tmp_path):
    failed = _failed_dir(monkeypatch, tmp_path)
    notes = []
    monkeypatch.setattr(talkhere, "notify", lambda *a, **k: notes.append(a))
    monkeypatch.setattr(talkhere, "transcribe_and_deliver",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cuda OOM")))
    wav = tmp_path / "utterance-1.wav"
    make_wav(wav, 2000)
    rc = talkhere.transcribe_or_keep(wav, {}, ns(), verbose=False)
    assert rc == 1                                              # loud failure, not exit 0
    assert not wav.exists() and (failed / "utterance-1.wav").exists()   # audio survives (P13)
    assert notes and "retry" in notes[0][1]                     # tells the user how to recover


def test_P13_unhandled_exception_is_logged_and_notified(monkeypatch):
    """A crash anywhere must not be a silent death: hotkey launches have no terminal."""
    logs, notes = [], []
    monkeypatch.setattr(talkhere, "log", lambda m: logs.append(m))
    monkeypatch.setattr(talkhere, "notify", lambda *a, **k: notes.append(a))
    monkeypatch.setattr(talkhere, "_dispatch",
                        lambda argv: (_ for _ in ()).throw(ValueError("boom")))
    assert talkhere.main([]) == 1                               # non-zero exit (E15)
    assert any("FATAL" in m and "boom" in m for m in logs)      # traceback in the log
    assert any("boom" in n[1] for n in notes)                   # and a desktop notification


def test_P13_retry_last_delivers_the_preserved_audio(monkeypatch, tmp_path):
    failed = _failed_dir(monkeypatch, tmp_path)
    failed.mkdir(parents=True)
    make_wav(failed / "utterance-1.wav", 2000)
    make_wav(failed / "utterance-2.wav", 2000)                  # the newest one wins
    sink = FakeSink()
    monkeypatch.setattr(talkhere, "resolve_backend", lambda cfg, args: FakeBackend("rattrapé"))
    monkeypatch.setattr(talkhere, "resolve_sink", lambda cfg, args: (sink, "type"))
    monkeypatch.setattr(talkhere, "_active_window", lambda: None)
    assert talkhere.main(["--retry-last"]) == 0
    assert sink.delivered == ["rattrapé "]                      # text recovered and delivered
    assert not (failed / "utterance-2.wav").exists()            # consumed, won't replay
    assert (failed / "utterance-1.wav").exists()                # older one untouched


def test_P13_retry_last_with_nothing_preserved_is_a_no_op(monkeypatch, tmp_path):
    _failed_dir(monkeypatch, tmp_path)
    assert talkhere.main(["--retry-last"]) == 0                 # a no-op, not an error


def test_P13_failed_dir_keeps_only_the_last_five(monkeypatch, tmp_path):
    failed = _failed_dir(monkeypatch, tmp_path)
    import os as _os
    for i in range(8):
        wav = tmp_path / f"u{i}.wav"
        make_wav(wav, 400)
        talkhere.keep_failed_wav(wav)
        _os.utime(failed / f"u{i}.wav", (1000 + i, 1000 + i))   # deterministic ordering
    kept = sorted(p.name for p in failed.glob("*.wav"))
    assert len(kept) == talkhere.FAILED_KEEP                    # bounded, no disk hog
    assert "u7.wav" in kept and "u0.wav" not in kept            # newest survive


def test_E6_int8_forced_to_float16_on_cuda(monkeypatch):
    monkeypatch.setattr(talkhere, "log", lambda *a: None)
    be = talkhere.LocalBackend("m", "cuda", "int8")             # int8 crashes on Blackwell
    assert be.compute_type == "float16"                         # overridden (E6)


def test_api_key_env_beats_keyring(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fromenv")
    assert talkhere.ApiBackend._key() == "sk-fromenv"


def test_api_no_key_returns_empty_and_does_not_log_key(monkeypatch):
    monkeypatch.setattr(talkhere.ApiBackend, "_key", staticmethod(lambda: None))
    logs = []
    monkeypatch.setattr(talkhere, "log", lambda m: logs.append(m))
    assert talkhere.ApiBackend("whisper-1").transcribe("x.wav", "auto") == ""
    assert not any("sk-" in m for m in logs)                    # NF6 / security: no key leak


def test_P9_no_recorder_is_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(talkhere, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(talkhere, "_recorder_cmd", lambda w: None)   # no pw-record/arecord
    notes = []
    monkeypatch.setattr(talkhere, "notify", lambda *a, **k: notes.append(a))
    rc = talkhere.cmd_once(2.0, {}, ns(), verbose=False)
    assert rc == 1 and notes                                        # exit 1 + a notification (P9/E2)


def test_paste_sink_sets_clipboard_then_pastes(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw.get("input")))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(talkhere.subprocess, "run", fake_run)
    talkhere.PasteSink(paste_key="ctrl+shift+v").deliver("héllo")
    assert calls[0][0][:2] == ["xclip", "-selection"] and calls[0][1] == "héllo"
    assert calls[1][0] == ["xdotool", "key", "--clearmodifiers", "ctrl+shift+v"]


# ---------------------------------------------------------------------------
# Integration (GPU) — self-skips when faster-whisper / cuda absent
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_local_backend_transcribes_speech():
    import os
    sample = os.environ.get("TALKHERE_TEST_WAV")
    if not sample or not os.path.exists(sample):
        pytest.skip("set TALKHERE_TEST_WAV to a speech wav to run the GPU integration test")
    be = talkhere.LocalBackend("large-v3-turbo", "cuda", "float16")
    if not be.available():
        pytest.skip("faster-whisper not installed")
    text = be.transcribe(sample, "auto")
    assert "country" in text.lower()              # jfk.wav ground truth
