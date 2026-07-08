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
    base = dict(once=None, status=False, lang=None, backend=None, sink=None, verbose=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _mute_feedback(monkeypatch):
    """Feedback (notify/sound) is best-effort UI; silence it so tests stay hermetic."""
    monkeypatch.setattr(talkhere, "notify", lambda *a, **k: None)
    monkeypatch.setattr(talkhere, "cue", lambda *a, **k: None)


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
