"""Unit tests for Text-to-Speech disk caching, voice manager, and Piper engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nova.tts.piper_engine import (
    PiperEngine,
    PiperVoiceManager,
    TTSDiskCache,
    VoiceDownloadError,
)


def test_tts_disk_cache_operations(tmp_path: Path) -> None:
    cache = TTSDiskCache(cache_dir=tmp_path)

    # Initial miss
    assert cache.get("hello world", "en_US-lessac-medium") is None

    # Put into cache
    fake_wav = b"RIFFfake_wav_data"
    cache.put("Hello World", "en_US-lessac-medium", fake_wav)

    # Hit (case insensitive / stripped)
    cached = cache.get("   hello world   ", "en_US-lessac-medium")
    assert cached == fake_wav

    # Clear cache
    cache.clear()
    assert cache.get("hello world", "en_US-lessac-medium") is None


def test_piper_voice_manager_validation(tmp_path: Path) -> None:
    mgr = PiperVoiceManager(models_dir=tmp_path)
    assert not mgr.is_voice_cached("en_US-lessac-medium")

    # Invalid voice raises ValueError
    with pytest.raises(ValueError, match="Unknown voice"):
        mgr.download_voice("unknown_celebrity_voice")


def test_piper_voice_manager_download_failure(tmp_path: Path) -> None:
    mgr = PiperVoiceManager(models_dir=tmp_path)

    with (
        patch("httpx.Client.get", side_effect=RuntimeError("Connection refused")),
        pytest.raises(VoiceDownloadError),
    ):
        mgr.download_voice("en_US-lessac-medium")


def test_piper_engine_synthesis_fallback(tmp_path: Path) -> None:
    cache = TTSDiskCache(cache_dir=tmp_path / "cache")
    voice_mgr = PiperVoiceManager(models_dir=tmp_path / "models")
    player = MagicMock()

    engine = PiperEngine(voice_manager=voice_mgr, cache=cache, player=player)

    # When Piper models are not downloaded, synthesis falls back cleanly to synthetic WAV
    wav_bytes = engine.synthesize("Volume turned up.")
    assert isinstance(wav_bytes, bytes)
    assert len(wav_bytes) > 44  # Valid WAV header + frames
    assert wav_bytes.startswith(b"RIFF")

    # Second call hits disk cache
    cached_wav = engine.synthesize("Volume turned up.")
    assert cached_wav == wav_bytes

    # Speak calls player
    engine.speak("Volume turned up.")
    player.play_wav.assert_called_once()

    # Stop calls player stop
    engine.stop()
    player.stop.assert_called_once()
