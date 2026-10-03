"""Unit tests for HotkeyListener and AudioPlayer."""

from __future__ import annotations

import io
import wave
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
import sounddevice as sd

from nova.audio.hotkey import HotkeyListener
from nova.audio.player import AudioPlayer


def test_hotkey_listener_simulation() -> None:
    press_called = False
    release_called = False

    def on_p() -> None:
        nonlocal press_called
        press_called = True

    def on_r() -> None:
        nonlocal release_called
        release_called = True

    listener = HotkeyListener(on_press=on_p, on_release=on_r)
    assert not listener.is_running
    assert not listener.is_pressed

    # Simulate press and release
    listener.simulate_press()
    assert listener.is_pressed
    assert press_called is True

    listener.simulate_release()
    assert not listener.is_pressed
    assert release_called is True


def test_hotkey_start_stop() -> None:
    listener = HotkeyListener()
    listener.start()
    assert listener.is_running
    listener.stop()
    assert not listener.is_running


def test_audio_player_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_play = MagicMock()
    monkeypatch.setattr("sounddevice.play", mock_play)
    mock_stop = MagicMock()
    monkeypatch.setattr("sounddevice.stop", mock_stop)

    player = AudioPlayer()
    assert not player.is_playing

    # Stop when idle does not crash
    player.stop()

    # Play empty audio does nothing
    player.play_array(np.zeros(0, dtype=np.float32))
    assert not player.is_playing

    # 16-bit WAV playback
    buf16 = io.BytesIO()
    with wave.open(buf16, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((np.zeros(1600, dtype=np.int16)).tobytes())
    player.play_wav(buf16.getvalue(), blocking=True)
    assert mock_play.called

    # 8-bit WAV playback
    buf8 = io.BytesIO()
    with wave.open(buf8, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)
        wf.setframerate(16000)
        wf.writeframes(bytes([128] * 1600))
    player.play_wav(buf8.getvalue())

    # 32-bit WAV playback
    buf32 = io.BytesIO()
    with wave.open(buf32, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(4)
        wf.setframerate(16000)
        wf.writeframes(np.zeros(1600, dtype=np.int32).tobytes())
    player.play_wav(buf32.getvalue())

    # Stop active playback
    player._is_playing = True
    player.stop()
    assert not player.is_playing
    mock_stop.assert_called_once()


def test_audio_player_device_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def error_play(*args: Any, **kwargs: Any) -> None:
        raise sd.PortAudioError("Error querying device -1")

    monkeypatch.setattr("sounddevice.play", error_play)
    player = AudioPlayer()
    # Graceful degradation without raising exception
    player.play_array(np.zeros(160, dtype=np.float32))
    assert not player.is_playing


def test_audio_player_invalid_wav() -> None:
    player = AudioPlayer()
    with pytest.raises(RuntimeError, match="Audio playback error"):
        player.play_wav(b"not a valid wav")


def test_audio_player_on_play_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_play = MagicMock()
    mock_wait = MagicMock()
    monkeypatch.setattr("sounddevice.play", mock_play)
    monkeypatch.setattr("sounddevice.wait", mock_wait)

    callback_called = False

    def on_play() -> None:
        nonlocal callback_called
        callback_called = True

    player = AudioPlayer(on_play_callback=on_play)
    player.play_array(np.zeros(160, dtype=np.float32), blocking=False)
    assert callback_called is True
    assert mock_play.called


def test_audio_player_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def bad_play(*args: Any, **kwargs: Any) -> None:
        raise ValueError("Unexpected driver crash")

    monkeypatch.setattr("sounddevice.play", bad_play)
    player = AudioPlayer()
    with pytest.raises(RuntimeError, match="Audio device playback error"):
        player.play_array(np.zeros(160, dtype=np.float32))
    assert not player.is_playing
