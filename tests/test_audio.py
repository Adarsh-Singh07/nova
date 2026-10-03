"""Unit tests for audio capture, device listing, and resampling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from nova.audio.capture import (
    AudioCapture,
    AudioDeviceInfo,
    AudioDeviceUnavailableError,
    NoMicrophoneError,
    get_default_input_device,
    get_default_output_device,
    list_input_devices,
    list_output_devices,
)


def test_list_audio_devices() -> None:
    inputs = list_input_devices()
    outputs = list_output_devices()

    assert isinstance(inputs, list)
    assert isinstance(outputs, list)

    for dev in inputs:
        assert dev.max_input_channels > 0
        assert dev.name

    for dev in outputs:
        assert dev.max_output_channels > 0
        assert dev.name


def test_default_devices() -> None:
    def_in = get_default_input_device()
    def_out = get_default_output_device()

    if list_input_devices():
        assert def_in is not None
        assert def_in.max_input_channels > 0

    if list_output_devices():
        assert def_out is not None
        assert def_out.max_output_channels > 0


def test_audio_capture_initialization() -> None:
    capture = AudioCapture(target_sample_rate=16000, chunk_duration_ms=30)
    assert not capture.is_recording
    assert capture.current_device is None


def test_audio_capture_device_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = list_input_devices()
    if not inputs:
        mock_dev = AudioDeviceInfo(
            index=0,
            name="Mock Microphone",
            max_input_channels=2,
            max_output_channels=0,
            default_sample_rate=16000.0,
            host_api=0,
        )
        monkeypatch.setattr("nova.audio.capture.list_input_devices", lambda: [mock_dev])
        inputs = [mock_dev]

    # 1. Resolve by explicit valid index
    capture = AudioCapture(device_name_or_index=inputs[0].index)
    resolved = capture._resolve_device()
    assert resolved.index == inputs[0].index

    # 2. Resolve by non-existent index raises AudioDeviceUnavailableError
    bad_capture = AudioCapture(device_name_or_index=999999)
    with pytest.raises(AudioDeviceUnavailableError):
        bad_capture._resolve_device()


def test_audio_capture_no_microphone_error() -> None:
    with patch("nova.audio.capture.list_input_devices", return_value=[]):
        capture = AudioCapture()
        with pytest.raises(NoMicrophoneError):
            capture._resolve_device()


def test_audio_callback_accumulation() -> None:
    capture = AudioCapture()
    capture._is_recording = True
    capture._device_info = (
        list_input_devices()[0]
        if list_input_devices()
        else AudioDeviceInfo(
            index=0,
            name="Mock Mic",
            max_input_channels=1,
            max_output_channels=0,
            default_sample_rate=16000.0,
            host_api=0,
        )
    )

    # Simulate 1 channel incoming chunk
    chunk = np.ones((480, 1), dtype=np.float32) * 0.1
    capture._audio_callback(chunk, 480, None, MagicMock())

    read = capture.read_chunk()
    assert read is not None
    assert len(read) > 0
    assert capture.read_chunk() is None


def test_audio_capture_start_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_stream = MagicMock()
    monkeypatch.setattr("sounddevice.InputStream", MagicMock(return_value=mock_stream))

    mock_dev = AudioDeviceInfo(
        index=0,
        name="Mock Mic",
        max_input_channels=1,
        max_output_channels=0,
        default_sample_rate=16000.0,
        host_api=0,
    )
    monkeypatch.setattr("nova.audio.capture.list_input_devices", lambda: [mock_dev])
    monkeypatch.setattr("nova.audio.capture.get_default_input_device", lambda: mock_dev)

    capture = AudioCapture(device_name_or_index=0)
    try:
        capture.start()
        assert capture.is_recording is True
        assert capture.current_device is not None
        mock_stream.start.assert_called_once()
        # Feed sample data via callback
        capture._audio_callback(np.zeros((480, 1), dtype=np.float32), 480, None, MagicMock())
    finally:
        audio = capture.stop()
        assert capture.is_recording is False
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert isinstance(audio, np.ndarray)
        assert len(audio) == 480
