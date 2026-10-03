"""Unit tests for Voice Activity Detection (VAD) and speech segmenter."""

from __future__ import annotations

import numpy as np

from nova.audio.vad import EnergyVAD, VADSegmenter


def test_energy_vad_compute_rms() -> None:
    # Silence has 0 RMS
    silence = np.zeros(480, dtype=np.float32)
    assert EnergyVAD.compute_rms(silence) == 0.0

    # Loud sine wave has significant RMS
    t = np.linspace(0, 0.03, 480, endpoint=False)
    loud = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    rms = EnergyVAD.compute_rms(loud)
    assert rms > 0.1


def test_energy_vad_speech_classification() -> None:
    vad = EnergyVAD(base_threshold=0.02)

    silence = np.zeros(480, dtype=np.float32)
    assert not vad.is_speech(silence)

    t = np.linspace(0, 0.03, 480, endpoint=False)
    speech = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    assert vad.is_speech(speech)


def test_vad_segmenter_speech_detection() -> None:
    segmenter = VADSegmenter(
        sample_rate=16000,
        speech_onset_frames=2,
        silence_timeout_seconds=0.2,
        min_speech_seconds=0.1,
    )

    silence_frame = np.zeros(480, dtype=np.float32)
    t = np.linspace(0, 0.03, 480, endpoint=False)
    speech_frame = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

    # 1. Feed initial silence -> no speech onset
    assert segmenter.process_frame(silence_frame) is None
    assert not segmenter.speech_started

    # 2. Feed 2 consecutive speech frames -> speech begins
    assert segmenter.process_frame(speech_frame) is None
    assert segmenter.process_frame(speech_frame) is None
    assert segmenter.speech_started is True

    # 3. Feed sustained speech frames
    for _ in range(5):
        assert segmenter.process_frame(speech_frame) is None

    # 4. Feed silence frames exceeding timeout (0.2s = ~7 frames at 30ms each)
    result = None
    for _ in range(10):
        res = segmenter.process_frame(silence_frame)
        if res is not None:
            result = res
            break

    assert result is not None
    assert isinstance(result, np.ndarray)
    assert len(result) > 0
    assert not segmenter.speech_started


def test_vad_segmenter_discards_short_clicks() -> None:
    segmenter = VADSegmenter(
        sample_rate=16000,
        speech_onset_frames=1,
        silence_timeout_seconds=0.1,
        min_speech_seconds=0.5,  # Requires at least 500ms
    )

    t = np.linspace(0, 0.03, 480, endpoint=False)
    click = (0.5 * np.sin(2 * np.pi * 800 * t)).astype(np.float32)
    silence = np.zeros(480, dtype=np.float32)

    # Only 1 speech frame (~30ms)
    segmenter.process_frame(click)

    # Then silence timeout
    result = None
    for _ in range(5):
        res = segmenter.process_frame(silence)
        if res is not None:
            result = res
            break

    # Too short -> discarded as click
    assert result is None
