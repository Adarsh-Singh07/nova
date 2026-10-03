"""Audio capture, voice activity detection, playback, and wake word."""

from nova.audio.capture import (
    AudioCapture,
    AudioDeviceDisconnectedError,
    AudioDeviceInfo,
    AudioDeviceUnavailableError,
    AudioError,
    NoMicrophoneError,
    get_default_input_device,
    get_default_output_device,
    list_input_devices,
    list_output_devices,
)
from nova.audio.hotkey import HotkeyListener
from nova.audio.player import AudioPlayer
from nova.audio.vad import EnergyVAD, VADSegmenter
from nova.audio.wakeword import WakeWordEngine

__all__ = [
    "AudioCapture",
    "AudioDeviceDisconnectedError",
    "AudioDeviceInfo",
    "AudioDeviceUnavailableError",
    "AudioError",
    "AudioPlayer",
    "EnergyVAD",
    "HotkeyListener",
    "NoMicrophoneError",
    "VADSegmenter",
    "WakeWordEngine",
    "get_default_input_device",
    "get_default_output_device",
    "list_input_devices",
    "list_output_devices",
]
