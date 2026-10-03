"""Settings pages package init."""

from nova.ui.settings.pages.actions import ActionsPage
from nova.ui.settings.pages.audio import AudioPage
from nova.ui.settings.pages.general import GeneralPage
from nova.ui.settings.pages.llm import LLMPage
from nova.ui.settings.pages.stt import STTPage
from nova.ui.settings.pages.tts import TTSPage

__all__ = [
    "ActionsPage",
    "AudioPage",
    "GeneralPage",
    "LLMPage",
    "STTPage",
    "TTSPage",
]
