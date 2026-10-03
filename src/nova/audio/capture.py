"""Microphone audio capture using sounddevice with device selection, resampling, and auto-reconnect.

Captures 16kHz float32 mono audio for VAD and Speech-to-Text inference.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1


class AudioError(Exception):
    """Base exception for audio subsystem failures."""


class NoMicrophoneError(AudioError):
    """Raised when no input recording device is found."""


class AudioDeviceUnavailableError(AudioError):
    """Raised when the requested audio device cannot be opened."""


class AudioDeviceDisconnectedError(AudioError):
    """Raised when an audio device is unplugged or disconnected mid-stream."""


@dataclass(frozen=True)
class AudioDeviceInfo:
    """Metadata describing an audio device."""

    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float
    host_api: int


def list_input_devices() -> list[AudioDeviceInfo]:
    """Enumerate all available audio input devices (microphones)."""
    devices: list[AudioDeviceInfo] = []
    try:
        raw_devices = sd.query_devices()
        for idx, dev in enumerate(raw_devices):
            if dev.get("max_input_channels", 0) > 0:
                devices.append(
                    AudioDeviceInfo(
                        index=idx,
                        name=str(dev.get("name", f"Device {idx}")),
                        max_input_channels=int(dev.get("max_input_channels", 0)),
                        max_output_channels=int(dev.get("max_output_channels", 0)),
                        default_sample_rate=float(dev.get("default_samplerate", 16000.0)),
                        host_api=int(dev.get("hostapi", 0)),
                    )
                )
    except Exception as e:
        logger.exception("Failed to query input audio devices")
        raise AudioError(f"Error querying audio devices: {e}") from e

    return devices


def list_output_devices() -> list[AudioDeviceInfo]:
    """Enumerate all available audio output devices (speakers/headphones)."""
    devices: list[AudioDeviceInfo] = []
    try:
        raw_devices = sd.query_devices()
        for idx, dev in enumerate(raw_devices):
            if dev.get("max_output_channels", 0) > 0:
                devices.append(
                    AudioDeviceInfo(
                        index=idx,
                        name=str(dev.get("name", f"Device {idx}")),
                        max_input_channels=int(dev.get("max_input_channels", 0)),
                        max_output_channels=int(dev.get("max_output_channels", 0)),
                        default_sample_rate=float(dev.get("default_samplerate", 16000.0)),
                        host_api=int(dev.get("hostapi", 0)),
                    )
                )
    except Exception as e:
        logger.exception("Failed to query output audio devices")
        raise AudioError(f"Error querying audio devices: {e}") from e

    return devices


def get_default_input_device() -> AudioDeviceInfo | None:
    """Retrieve the system default microphone device."""
    devices = list_input_devices()
    if not devices:
        return None
    try:
        default_idx = sd.default.device[0]
        if default_idx is not None and default_idx >= 0:
            for dev in devices:
                if dev.index == default_idx:
                    return dev
    except Exception:
        pass
    return devices[0]


def get_default_output_device() -> AudioDeviceInfo | None:
    """Retrieve the system default speaker/output device."""
    devices = list_output_devices()
    if not devices:
        return None
    try:
        default_idx = sd.default.device[1]
        if default_idx is not None and default_idx >= 0:
            for dev in devices:
                if dev.index == default_idx:
                    return dev
    except Exception:
        pass
    return devices[0]


class AudioCapture:
    """Thread-safe non-blocking audio capture stream with software resampling to 16kHz mono."""

    def __init__(
        self,
        device_name_or_index: str | int | None = None,
        target_sample_rate: int = TARGET_SAMPLE_RATE,
        chunk_duration_ms: int = 30,
    ) -> None:
        self.target_sample_rate = target_sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.target_chunk_size = int(target_sample_rate * (chunk_duration_ms / 1000.0))

        self._device_spec = device_name_or_index
        self._device_info: AudioDeviceInfo | None = None
        self._stream: sd.InputStream | None = None
        self._is_recording = False
        self._lock = threading.RLock()
        self._buffer: list[np.ndarray[Any, Any]] = []

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    @property
    def current_device(self) -> AudioDeviceInfo | None:
        with self._lock:
            return self._device_info

    def _resolve_device(self) -> AudioDeviceInfo:
        """Resolve the requested device or fallback to the system default."""
        inputs = list_input_devices()
        if not inputs:
            raise NoMicrophoneError("No microphone or audio capture hardware detected on system.")

        if self._device_spec is None:
            default_dev = get_default_input_device()
            if default_dev:
                return default_dev
            return inputs[0]

        if isinstance(self._device_spec, int):
            for dev in inputs:
                if dev.index == self._device_spec:
                    return dev
            raise AudioDeviceUnavailableError(f"Input device index {self._device_spec} not found.")

        # Match by name (substring case-insensitive)
        spec_lower = str(self._device_spec).lower()
        for dev in inputs:
            if spec_lower in dev.name.lower():
                return dev

        logger.warning("Device '%s' not found. Falling back to default input.", self._device_spec)
        default_dev = get_default_input_device()
        return default_dev or inputs[0]

    def _audio_callback(
        self,
        indata: np.ndarray[Any, Any],
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback invoked by PortAudio thread on each captured audio chunk."""
        if status:
            logger.warning("PortAudio stream status flag: %s", status)

        with self._lock:
            if not self._is_recording:
                return

            data = indata.copy()
            # Convert multi-channel to mono if necessary
            if data.ndim > 1 and data.shape[1] > 1:
                data = np.mean(data, axis=1, keepdims=False)
            elif data.ndim > 1 and data.shape[1] == 1:
                data = data.squeeze(axis=1)

            # Resample to 16kHz if hardware sample rate differs
            if (
                self._device_info
                and int(self._device_info.default_sample_rate) != self.target_sample_rate
            ):
                orig_rate = int(self._device_info.default_sample_rate)
                # Resample using polyphase filtering
                data = resample_poly(data, self.target_sample_rate, orig_rate).astype(np.float32)

            self._buffer.append(data.astype(np.float32))

    def start(self) -> None:
        """Open the microphone stream and begin accumulating audio chunks."""
        with self._lock:
            if self._is_recording:
                return

            self._device_info = self._resolve_device()
            self._buffer.clear()

            hardware_rate = int(self._device_info.default_sample_rate)
            # Choose block size matching chunk duration at hardware rate
            block_size = int(hardware_rate * (self.chunk_duration_ms / 1000.0))

            try:
                self._stream = sd.InputStream(
                    device=self._device_info.index,
                    channels=1,
                    samplerate=hardware_rate,
                    blocksize=block_size,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._is_recording = True
                logger.info(
                    "Started audio capture on device '%s' (hw_rate=%d, target_rate=%d)",
                    self._device_info.name,
                    hardware_rate,
                    self.target_sample_rate,
                )
            except Exception as e:
                logger.exception("Failed to open audio input stream on %s", self._device_info.name)
                raise AudioDeviceUnavailableError(
                    f"Could not open microphone '{self._device_info.name}': {e}"
                ) from e

    def stop(self) -> np.ndarray[Any, Any]:
        """Stop audio capture and return the accumulated 16kHz float32 audio array."""
        with self._lock:
            self._is_recording = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.warning("Error closing audio stream: %s", e)
                finally:
                    self._stream = None

            if not self._buffer:
                return np.zeros(0, dtype=np.float32)

            audio_data = np.concatenate(self._buffer, axis=0)
            self._buffer.clear()
            logger.debug(
                "Captured %d audio samples (%.2f seconds)",
                len(audio_data),
                len(audio_data) / self.target_sample_rate,
            )
            return cast("np.ndarray[Any, Any]", audio_data)

    def read_chunk(self) -> np.ndarray[Any, Any] | None:
        """Retrieve and pop the oldest captured audio chunk, if available."""
        with self._lock:
            if self._buffer:
                return self._buffer.pop(0)
            return None
