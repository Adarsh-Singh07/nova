"""Unit tests for HotkeyListener and AudioPlayer."""

from __future__ import annotations

import io
import wave

import numpy as np

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


def test_audio_player_operations() -> None:
    player = AudioPlayer()
    assert not player.is_playing

    # Stop when idle does not crash
    player.stop()

    # Play empty audio does nothing
    player.play_array(np.zeros(0, dtype=np.float32))
    assert not player.is_playing

    # Create dummy valid WAV in memory
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((np.zeros(1600, dtype=np.int16)).tobytes())
    wav_bytes = buf.getvalue()
    player.play_wav(wav_bytes)

    # Stop playback
    player.stop()
    assert not player.is_playing
