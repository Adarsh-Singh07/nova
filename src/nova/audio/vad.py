"""Voice Activity Detection (VAD) and automatic speech endpointing.

Uses RMS energy thresholding with dynamic ambient noise floor tracking to detect
when user starts and stops speaking.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import numpy as np

logger = logging.getLogger(__name__)


class EnergyVAD:
    """Fast, lightweight energy-based Voice Activity Detector."""

    def __init__(
        self,
        base_threshold: float = 0.015,
        ambient_alpha: float = 0.95,
    ) -> None:
        self.base_threshold = base_threshold
        self.ambient_alpha = ambient_alpha
        self.ambient_noise_level = base_threshold / 2.0

    @staticmethod
    def compute_rms(frame: np.ndarray[Any, Any]) -> float:
        """Calculate Root Mean Square (RMS) energy of an audio frame."""
        if len(frame) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))

    def is_speech(self, frame: np.ndarray[Any, Any]) -> bool:
        """Determine if an audio frame contains human speech activity."""
        rms = self.compute_rms(frame)

        # Dynamic threshold: higher of base threshold or 2.5x current ambient noise
        dynamic_threshold = max(self.base_threshold, self.ambient_noise_level * 2.5)
        is_active = rms > dynamic_threshold

        # Update ambient noise estimation when silence
        if not is_active:
            self.ambient_noise_level = (
                self.ambient_alpha * self.ambient_noise_level + (1.0 - self.ambient_alpha) * rms
            )

        return is_active

    def reset(self) -> None:
        """Reset ambient noise tracker to defaults."""
        self.ambient_noise_level = self.base_threshold / 2.0


class VADSegmenter:
    """Accumulates audio frames and detects complete speech utterances."""

    def __init__(
        self,
        sample_rate: int = 16000,
        vad: EnergyVAD | None = None,
        speech_onset_frames: int = 3,  # ~90ms to trigger speech start
        silence_timeout_seconds: float = 0.8,  # ~800ms of silence to trigger end
        min_speech_seconds: float = 0.4,  # ignore clicks < 400ms
        max_speech_seconds: float = 15.0,  # maximum speech window limit
    ) -> None:
        self.sample_rate = sample_rate
        self.vad = vad or EnergyVAD()
        self.speech_onset_frames = speech_onset_frames
        self.silence_timeout_seconds = silence_timeout_seconds
        self.min_speech_seconds = min_speech_seconds
        self.max_speech_seconds = max_speech_seconds

        self._consecutive_speech_frames = 0
        self._consecutive_silence_samples = 0
        self._speech_started = False
        self._accumulated_chunks: list[np.ndarray[Any, Any]] = []
        self._total_samples = 0

    @property
    def speech_started(self) -> bool:
        return self._speech_started

    def process_frame(self, frame: np.ndarray[Any, Any]) -> np.ndarray[Any, Any] | None:
        """Process an incoming audio frame.

        Returns:
            np.ndarray of complete speech segment if utterance has ended, else None.
        """
        is_speech = self.vad.is_speech(frame)
        frame_samples = len(frame)

        if not self._speech_started:
            if is_speech:
                self._consecutive_speech_frames += 1
                self._accumulated_chunks.append(frame)
                if self._consecutive_speech_frames >= self.speech_onset_frames:
                    self._speech_started = True
                    self._consecutive_silence_samples = 0
                    logger.debug("VAD: Speech onset detected.")
            else:
                self._consecutive_speech_frames = 0
                # Keep a small pre-roll buffer (up to ~3 frames) to capture voice onset cleanly
                self._accumulated_chunks.append(frame)
                if len(self._accumulated_chunks) > 4:
                    self._accumulated_chunks.pop(0)
            return None

        # Speech is currently active
        self._accumulated_chunks.append(frame)
        self._total_samples += frame_samples

        if is_speech:
            self._consecutive_silence_samples = 0
        else:
            self._consecutive_silence_samples += frame_samples

        # Check for end of speech (silence timeout or max duration reached)
        silence_sec = self._consecutive_silence_samples / self.sample_rate
        total_sec = self._total_samples / self.sample_rate

        if silence_sec >= self.silence_timeout_seconds or total_sec >= self.max_speech_seconds:
            logger.debug(
                "VAD: Speech concluded (total=%.2fs, silence=%.2fs)",
                total_sec,
                silence_sec,
            )
            result = self.flush()
            if total_sec >= self.min_speech_seconds:
                return result
            # Too short; discard as noise/transient click
            logger.debug(
                "VAD: Utterance discarded (below min duration %.2fs)", self.min_speech_seconds
            )
            return None

        return None

    def flush(self) -> np.ndarray[Any, Any]:
        """Finalize and return all accumulated speech samples."""
        if not self._accumulated_chunks:
            self.reset()
            return np.zeros(0, dtype=np.float32)

        speech_data = np.concatenate(self._accumulated_chunks, axis=0)
        self.reset()
        return cast("np.ndarray[Any, Any]", speech_data.astype(np.float32))

    def reset(self) -> None:
        """Reset segmenter internal tracking state."""
        self._speech_started = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_samples = 0
        self._accumulated_chunks.clear()
        self._total_samples = 0
        self.vad.reset()
