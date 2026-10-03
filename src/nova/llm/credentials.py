"""Secure credentials access and keyring storage for NOVA LLM providers.

Enforces Rule R5.3: API keys are accessed from environment variables or the OS
keyring (Windows Credential Manager / Secret Service). Never stored in plaintext
config files or git.
"""

from __future__ import annotations

import logging
import os

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "nova"
KEY_GEMINI = "gemini_api_key"
KEY_AGNES = "agnes_api_key"


def get_gemini_api_key() -> str | None:
    """Retrieve Gemini API key from environment variable or OS keyring."""
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    if keyring is not None:
        try:
            stored = keyring.get_password(KEYRING_SERVICE, KEY_GEMINI)
            if stored and stored.strip():
                return stored.strip()
        except Exception:
            logger.debug("Failed to read Gemini key from keyring", exc_info=True)
    return None


def set_gemini_api_key(key: str) -> None:
    """Save Gemini API key to active environment and OS keyring."""
    clean = key.strip()
    os.environ["GEMINI_API_KEY"] = clean
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, KEY_GEMINI, clean)
        except Exception:
            logger.warning("Failed to persist Gemini API key to OS keyring")


def get_agnes_api_key() -> str | None:
    """Retrieve Agnes API key from environment variable or OS keyring."""
    env_key = os.environ.get("AGNES_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    if keyring is not None:
        try:
            stored = keyring.get_password(KEYRING_SERVICE, KEY_AGNES)
            if stored and stored.strip():
                return stored.strip()
        except Exception:
            logger.debug("Failed to read Agnes key from keyring", exc_info=True)
    return None


def set_agnes_api_key(key: str) -> None:
    """Save Agnes API key to active environment and OS keyring."""
    clean = key.strip()
    os.environ["AGNES_API_KEY"] = clean
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, KEY_AGNES, clean)
        except Exception:
            logger.warning("Failed to persist Agnes API key to OS keyring")


def get_agnes_base_url() -> str:
    """Retrieve Agnes API base URL."""
    return os.environ.get("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")


def get_agnes_model() -> str:
    """Retrieve Agnes default chat model."""
    return os.environ.get("AGNES_CHAT_MODEL", "agnes-3.0-flash")
