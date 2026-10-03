"""Speech-to-Text inference engine powered by faster-whisper (CTranslate2).

Provides fast, private, offline transcription with model download management and
INT8 CPU quantization.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import platformdirs

from nova.core.interfaces import STTEngineProtocol, TranscriptionResult

logger = logging.getLogger(__name__)

APP_NAME = "nova"
APP_AUTHOR = "Adarsh Singh"
DEFAULT_MODEL_SIZE = "base.en"


class STTError(Exception):
    """Base exception for Speech-to-Text failures."""


class ModelDownloadError(STTError):
    """Raised when an STT model fails to download or verify."""


class ModelManager:
    """Manages downloading, verifying, and caching faster-whisper model weights."""

    SUPPORTED_MODELS: ClassVar[set[str]] = {"tiny.en", "base.en", "small.en"}

    def __init__(self, cache_dir: Path | None = None) -> None:
        if cache_dir is None:
            self.cache_dir = (
                Path(platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR)) / "models" / "whisper"
            )
        else:
            self.cache_dir = cache_dir

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def is_model_cached(self, model_size: str) -> bool:
        """Check if model weights already exist in the local cache."""
        model_path = self.cache_dir / model_size
        return model_path.exists() and any(model_path.iterdir())

    def get_model_path(self, model_size: str) -> Path:
        """Return the target directory path for a model."""
        return self.cache_dir / model_size

    def download_model(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Download model weights using faster-whisper utilities with caching and resume."""
        if model_size not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model '{model_size}'. Supported: {sorted(self.SUPPORTED_MODELS)}"
            )

        target_dir = self.cache_dir / model_size
        if self.is_model_cached(model_size):
            logger.debug("Model '%s' already cached at %s", model_size, target_dir)
            return target_dir

        logger.info("Downloading faster-whisper model '%s' to %s...", model_size, target_dir)

        try:
            from faster_whisper.utils import download_model

            # download_model automatically handles verification, caching, and resume
            downloaded_path = download_model(
                size_or_id=model_size,
                output_dir=str(target_dir),
            )
            logger.info("Model '%s' successfully downloaded to %s", model_size, downloaded_path)
            return Path(downloaded_path)

        except Exception as e:
            logger.exception("Failed to download model '%s'", model_size)
            raise ModelDownloadError(
                f"Could not download model '{model_size}'. Check your internet connection or offline status. Error: {e}"
            ) from e


class WhisperEngine(STTEngineProtocol):
    """faster-whisper STT engine running quantized INT8 inference on CPU."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        model_manager: ModelManager | None = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.model_manager = model_manager or ModelManager()

        self._model: Any = None
        self._is_loaded = False
        self._lock = threading.RLock()

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self._is_loaded

    def is_available(self) -> bool:
        """Return True if model is loaded or cached locally."""
        with self._lock:
            if self._is_loaded:
                return True
            return self.model_manager.is_model_cached(self.model_size)

    def load_model(self) -> None:
        """Load model into memory, downloading if necessary."""
        with self._lock:
            if self._is_loaded and self._model is not None:
                return

            model_dir = self.model_manager.download_model(self.model_size)
            logger.info(
                "Loading faster-whisper (%s, device=%s, compute=%s)...",
                self.model_size,
                self.device,
                self.compute_type,
            )

            try:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(
                    model_size_or_path=str(model_dir),
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.cpu_threads,
                )
                self._is_loaded = True
                logger.info("faster-whisper model '%s' loaded and ready.", self.model_size)
            except Exception as e:
                logger.exception("Failed to initialize WhisperModel from %s", model_dir)
                raise STTError(f"Error loading Whisper model: {e}") from e

    def transcribe(self, audio_data: np.ndarray[Any, Any]) -> TranscriptionResult:
        """Transcribe a 16kHz float32 mono audio NumPy array into text."""
        if len(audio_data) == 0:
            return TranscriptionResult(text="", confidence=1.0, duration_seconds=0.0)

        with self._lock:
            if not self._is_loaded or self._model is None:
                self.load_model()

            duration = float(len(audio_data)) / 16000.0

            try:
                # audio_data must be 1D float32 array
                if audio_data.dtype != np.float32:
                    audio_data = audio_data.astype(np.float32)

                segments, info = self._model.transcribe(
                    audio_data,
                    beam_size=1,  # greedy search for maximum CPU speed (latency < 250ms)
                    language="en",
                    task="transcribe",
                    vad_filter=False,  # VAD is already executed by NOVA audio layer
                )

                text_parts: list[str] = []
                prob_parts: list[float] = []

                for segment in segments:
                    text_parts.append(segment.text)
                    if hasattr(segment, "avg_logprob"):
                        prob_parts.append(float(np.exp(segment.avg_logprob)))

                full_text = " ".join(text_parts).strip()
                avg_confidence = float(np.mean(prob_parts)) if prob_parts else 0.95

                logger.debug(
                    "STT: Transcribed %.2fs of audio -> '%s' (conf=%.2f)",
                    duration,
                    full_text,
                    avg_confidence,
                )

                return TranscriptionResult(
                    text=full_text,
                    confidence=avg_confidence,
                    language=info.language if hasattr(info, "language") else "en",
                    duration_seconds=duration,
                )

            except Exception as e:
                logger.exception("Error during speech transcription")
                raise STTError(f"Transcription failed: {e}") from e
