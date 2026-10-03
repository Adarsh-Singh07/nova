"""Offline local wake word detection using openWakeWord ONNX models.

Listens continuously on 16kHz audio streams for 'Hey Nova' wake word activation.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class WakeWordEngine:
    """Offline neural wake word classifier utilizing openWakeWord ONNX models."""

    def __init__(
        self,
        wake_phrase: str = "hey nova",
        threshold: float = 0.5,
        on_wake: Callable[[str], None] | None = None,
    ) -> None:
        self.wake_phrase = wake_phrase.lower()
        self.threshold = threshold
        self.on_wake = on_wake

        self._model: Any = None
        self._is_initialized = False
        self._lock = threading.RLock()

    @property
    def is_initialized(self) -> bool:
        with self._lock:
            return self._is_initialized

    def initialize(self) -> bool:
        """Load openWakeWord models into memory."""
        with self._lock:
            if self._is_initialized:
                return True

            try:
                from openwakeword.model import Model

                # Load pretrained model or default available models
                self._model = Model(inference_framework="onnx")
                self._is_initialized = True
                logger.info(
                    "openWakeWord engine initialized successfully with available models: %s",
                    list(self._model.models.keys()) if hasattr(self._model, "models") else [],
                )
                return True
            except Exception as e:
                logger.warning("Could not initialize openWakeWord: %s. Wake word disabled.", e)
                self._is_initialized = False
                return False

    def predict(self, frame_16khz: np.ndarray[Any, Any]) -> float:
        """Score an incoming audio chunk (expects 1280 samples / 80ms at 16kHz)."""
        with self._lock:
            if not self._is_initialized or self._model is None:
                return 0.0

            try:
                # openwakeword expects 16-bit signed integer PCM in range [-32768, 32767]
                if frame_16khz.dtype == np.float32:
                    pcm16 = (frame_16khz * 32767.0).astype(np.int16)
                else:
                    pcm16 = frame_16khz.astype(np.int16)

                prediction = self._model.predict(pcm16)

                max_score = 0.0
                for model_name, score in prediction.items():
                    if score > max_score:
                        max_score = float(score)

                    if score >= self.threshold:
                        logger.info("Wake word detected! Model: %s (score=%.3f)", model_name, score)
                        if self.on_wake:
                            try:
                                self.on_wake(model_name)
                            except Exception:
                                logger.exception("Error in wake word callback")

                return max_score
            except Exception as e:
                logger.error("Error during wake word prediction: %s", e)
                return 0.0

    def reset(self) -> None:
        """Reset openWakeWord buffer states."""
        with self._lock:
            if self._model is not None and hasattr(self._model, "reset"):
                with contextlib.suppress(Exception):
                    self._model.reset()
