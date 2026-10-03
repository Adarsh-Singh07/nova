"""Local neural Text-to-Speech synthesis using Piper with on-disk WAV caching.

Provides offline, high-speed, natural speech synthesis with instant replay from cache.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import logging
import threading
import wave
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import platformdirs

from nova.audio.player import AudioPlayer
from nova.core.interfaces import TTSEngineProtocol

logger = logging.getLogger(__name__)

APP_NAME = "nova"
APP_AUTHOR = "Adarsh Singh"
DEFAULT_VOICE = "en_US-lessac-medium"

# Verified Piper voice model endpoints (Public Domain / CC0)
PIPER_VOICE_URLS: dict[str, tuple[str, str]] = {
    "en_US-lessac-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    ),
    "en_US-ryan-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json",
    ),
}


class TTSError(Exception):
    """Base exception for Text-to-Speech failures."""


class VoiceDownloadError(TTSError):
    """Raised when a Piper neural voice checkpoint fails to download."""


class TTSDiskCache:
    """Persistent on-disk cache for synthesized audio responses."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        if cache_dir is None:
            self.cache_dir = (
                Path(platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR)) / "cache" / "tts"
            )
        else:
            self.cache_dir = cache_dir

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(self, text: str, voice: str) -> str:
        clean_text = text.strip().lower()
        combined = f"{voice.lower()}:{clean_text}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(self, text: str, voice: str) -> bytes | None:
        """Retrieve cached WAV bytes if available."""
        key = self._make_key(text, voice)
        cache_file = self.cache_dir / f"{key}.wav"
        if cache_file.exists():
            try:
                data = cache_file.read_bytes()
                logger.debug("TTS Cache HIT for '%s' (%d bytes)", text, len(data))
                return data
            except Exception:
                logger.warning("Failed to read TTS cache file %s", cache_file)
        return None

    def put(self, text: str, voice: str, wav_bytes: bytes) -> None:
        """Store synthesized WAV bytes into cache."""
        if not wav_bytes:
            return
        key = self._make_key(text, voice)
        cache_file = self.cache_dir / f"{key}.wav"
        try:
            cache_file.write_bytes(wav_bytes)
            logger.debug("TTS Cache STORE for '%s'", text)
        except Exception:
            logger.warning("Failed to write to TTS cache: %s", cache_file)

    def clear(self) -> None:
        """Delete all cached audio files."""
        for file in self.cache_dir.glob("*.wav"):
            with contextlib.suppress(Exception):
                file.unlink()


class PiperVoiceManager:
    """Manages Piper neural voice checkpoint downloading and validation."""

    def __init__(self, models_dir: Path | None = None) -> None:
        if models_dir is None:
            self.models_dir = (
                Path(platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR)) / "models" / "piper"
            )
        else:
            self.models_dir = models_dir

        self.models_dir.mkdir(parents=True, exist_ok=True)

    def is_voice_cached(self, voice_name: str) -> bool:
        """Check if ONNX model and JSON config exist on disk."""
        onnx_file = self.models_dir / f"{voice_name}.onnx"
        json_file = self.models_dir / f"{voice_name}.onnx.json"
        return onnx_file.exists() and json_file.exists() and onnx_file.stat().st_size > 1000

    def download_voice(self, voice_name: str = DEFAULT_VOICE) -> tuple[Path, Path]:
        """Download voice ONNX and JSON files if not present."""
        if voice_name not in PIPER_VOICE_URLS:
            raise ValueError(
                f"Unknown voice '{voice_name}'. Supported: {list(PIPER_VOICE_URLS.keys())}"
            )

        onnx_path = self.models_dir / f"{voice_name}.onnx"
        json_path = self.models_dir / f"{voice_name}.onnx.json"

        if self.is_voice_cached(voice_name):
            logger.debug("Voice '%s' already cached on disk.", voice_name)
            return onnx_path, json_path

        onnx_url, json_url = PIPER_VOICE_URLS[voice_name]
        logger.info("Downloading Piper voice '%s' from HuggingFace...", voice_name)

        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                # 1. Download JSON config
                r_json = client.get(json_url)
                r_json.raise_for_status()
                json_path.write_bytes(r_json.content)

                # 2. Download ONNX model weights
                r_onnx = client.get(onnx_url)
                r_onnx.raise_for_status()
                onnx_path.write_bytes(r_onnx.content)

            logger.info(
                "Piper voice '%s' downloaded successfully to %s", voice_name, self.models_dir
            )
            return onnx_path, json_path

        except Exception as e:
            logger.exception("Failed to download Piper voice '%s'", voice_name)
            raise VoiceDownloadError(f"Error downloading voice '{voice_name}': {e}") from e


class PiperEngine(TTSEngineProtocol):
    """Local Piper neural TTS engine with disk caching and live playback."""

    def __init__(
        self,
        default_voice: str = DEFAULT_VOICE,
        voice_manager: PiperVoiceManager | None = None,
        cache: TTSDiskCache | None = None,
        player: AudioPlayer | None = None,
    ) -> None:
        self.default_voice = default_voice
        self.voice_manager = voice_manager or PiperVoiceManager()
        self.cache = cache or TTSDiskCache()
        if player is None:

            def _unmute_hook() -> None:
                with contextlib.suppress(Exception):
                    from nova.platform import get_platform_adapter

                    get_platform_adapter().unmute_current_process()

            self.player = AudioPlayer(on_play_callback=_unmute_hook)
        else:
            self.player = player

        self._piper_voice: Any = None
        self._loaded_voice_name: str | None = None
        self._lock = threading.RLock()

    def is_available(self) -> bool:
        """Return True if voice checkpoint is cached on disk."""
        return self.voice_manager.is_voice_cached(self.default_voice)

    def _ensure_voice_loaded(self, voice_name: str) -> Any:
        """Load PiperVoice model into memory."""
        with self._lock:
            if self._piper_voice is not None and self._loaded_voice_name == voice_name:
                return self._piper_voice

            onnx_path, json_path = self.voice_manager.download_voice(voice_name)
            try:
                from piper.voice import PiperVoice

                self._piper_voice = PiperVoice.load(
                    model_path=onnx_path,
                    config_path=json_path,
                    use_cuda=False,
                )
                self._loaded_voice_name = voice_name
                logger.info("Piper neural voice '%s' loaded into memory.", voice_name)
                return self._piper_voice
            except Exception as e:
                logger.exception("Failed to load PiperVoice from %s", onnx_path)
                raise TTSError(f"Error loading Piper voice '{voice_name}': {e}") from e

    def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into standard WAV audio bytes, with disk caching."""
        clean_text = text.strip()
        if not clean_text:
            return b""

        target_voice = voice or self.default_voice

        # 1. Check persistent on-disk cache (immediate < 5ms return)
        cached = self.cache.get(clean_text, target_voice)
        if cached is not None:
            return cached

        # 2. Synthesize using Piper neural model
        with self._lock:
            try:
                piper_voice = self._ensure_voice_loaded(target_voice)
                buffer = io.BytesIO()
                with wave.open(buffer, "wb") as wav_file:
                    piper_voice.synthesize_wav(clean_text, wav_file)

                wav_bytes = buffer.getvalue()
                # Store into cache
                self.cache.put(clean_text, target_voice, wav_bytes)
                return wav_bytes

            except Exception as e:
                logger.warning("Piper synthesis failed (%s). Falling back to synthetic tone.", e)
                fallback_wav = self._generate_fallback_wav(clean_text)
                self.cache.put(clean_text, target_voice, fallback_wav)
                return fallback_wav

    def speak(self, text: str, voice: str | None = None, blocking: bool = False) -> None:
        """Synthesize text and play aloud through the audio player."""
        wav_bytes = self.synthesize(text, voice)
        if wav_bytes:
            self.player.play_wav(wav_bytes, blocking=blocking)

    def stop(self) -> None:
        """Immediately abort active playback."""
        self.player.stop()

    @staticmethod
    def _generate_fallback_wav(text: str) -> bytes:
        """Generate a clean synthetic sine audio WAV as emergency fallback."""
        sample_rate = 16000
        duration = min(3.0, max(0.5, len(text) * 0.05))
        num_samples = int(sample_rate * duration)
        # Gentle 440Hz tone with fade-in and fade-out
        t = np.linspace(0, duration, num_samples, endpoint=False)
        envelope = np.sin(np.pi * np.linspace(0, 1, num_samples)) ** 2
        samples = (0.2 * np.sin(2 * np.pi * 440.0 * t) * envelope).astype(np.float32)

        pcm16 = (samples * 32767.0).astype(np.int16)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm16.tobytes())

        return buffer.getvalue()
