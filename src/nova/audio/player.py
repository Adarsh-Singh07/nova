"""Audio playback engine for spoken responses and audio cues using sounddevice.

Supports non-blocking playback of WAV byte streams and NumPy audio arrays with
immediate cancellation support.
"""

from __future__ import annotations

import contextlib
import io
import logging
import threading
import wave
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Non-blocking audio player supporting WAV bytes and NumPy PCM arrays."""

    def __init__(
        self,
        output_device_name_or_index: str | int | None = None,
        on_play_callback: Callable[[], None] | None = None,
    ) -> None:
        self.device = output_device_name_or_index
        self.on_play_callback = on_play_callback
        self._is_playing = False
        self._lock = threading.RLock()

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._is_playing

    def play_wav(self, wav_bytes: bytes, blocking: bool = False) -> None:
        """Play a standard WAV byte buffer through the output device."""
        if not wav_bytes:
            return

        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                num_frames = wf.getnframes()
                raw_data = wf.readframes(num_frames)

            # Convert raw bytes to normalized float32 array
            if sample_width == 2:  # 16-bit PCM
                pcm16 = np.frombuffer(raw_data, dtype=np.int16)
                audio_array = (pcm16.astype(np.float32) / 32768.0).reshape(-1, channels)
            elif sample_width == 1:  # 8-bit unsigned
                pcm8 = np.frombuffer(raw_data, dtype=np.uint8)
                audio_array = ((pcm8.astype(np.float32) - 128.0) / 128.0).reshape(-1, channels)
            else:
                pcm32 = np.frombuffer(raw_data, dtype=np.int32)
                audio_array = (pcm32.astype(np.float32) / 2147483648.0).reshape(-1, channels)

            self.play_array(audio_array, sample_rate=sample_rate, blocking=blocking)

        except Exception as e:
            logger.exception("Error decoding or playing WAV audio buffer")
            raise RuntimeError(f"Audio playback error: {e}") from e

    def play_array(
        self,
        audio_data: np.ndarray[Any, Any],
        sample_rate: int = 16000,
        blocking: bool = False,
    ) -> None:
        """Play an in-memory NumPy audio array."""
        if len(audio_data) == 0:
            return

        with self._lock:
            self._is_playing = True

        def _finished_callback() -> None:
            with self._lock:
                self._is_playing = False

        try:
            sd.play(
                audio_data,
                samplerate=sample_rate,
                device=self.device,
                blocking=blocking,
            )
            if self.on_play_callback is not None:
                with contextlib.suppress(Exception):
                    self.on_play_callback()

            if blocking:
                _finished_callback()
            else:

                def _wait_and_finish() -> None:
                    with contextlib.suppress(Exception):
                        sd.wait()
                    with self._lock:
                        self._is_playing = False

                threading.Thread(target=_wait_and_finish, daemon=True).start()
        except sd.PortAudioError as e:
            with self._lock:
                self._is_playing = False
            logger.warning("Audio playback device unavailable: %s", e)
        except Exception as e:
            with self._lock:
                self._is_playing = False
            logger.exception("Failed to play audio on output device %s", self.device)
            raise RuntimeError(f"Audio device playback error: {e}") from e

    def stop(self) -> None:
        """Immediately abort active audio playback."""
        with self._lock:
            if self._is_playing:
                try:
                    sd.stop()
                    logger.debug("Audio playback aborted.")
                except Exception as e:
                    logger.warning("Error stopping audio output: %s", e)
                finally:
                    self._is_playing = False
