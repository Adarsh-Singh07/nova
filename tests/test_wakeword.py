"""Unit tests for openWakeWord detection engine."""

from __future__ import annotations

import numpy as np

from nova.audio.wakeword import WakeWordEngine


def test_wakeword_uninitialized_predict() -> None:
    engine = WakeWordEngine(wake_phrase="hey nova")
    assert not engine.is_initialized

    chunk = np.zeros(1280, dtype=np.float32)
    score = engine.predict(chunk)
    assert score == 0.0


def test_wakeword_initialization_and_reset() -> None:
    engine = WakeWordEngine()
    # If openwakeword can load on this system
    initialized = engine.initialize()
    if initialized:
        assert engine.is_initialized
        chunk = np.zeros(1280, dtype=np.float32)
        score = engine.predict(chunk)
        assert isinstance(score, float)
        engine.reset()
