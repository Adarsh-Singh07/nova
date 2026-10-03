"""Core pipeline, state machine, settings, and intent engine for NOVA."""

from nova.core.actions import ActionID, AllowlistValidator
from nova.core.fakes import (
    FakeConfirmationHandler,
    FakeIntentEngine,
    FakePlatformAdapter,
    FakeSTTEngine,
    FakeTTSEngine,
)
from nova.core.interfaces import (
    ActionRequest,
    ActionResult,
    ConfirmationHandlerProtocol,
    IntentEngineProtocol,
    PlatformAdapterProtocol,
    STTEngineProtocol,
    TranscriptionResult,
    TTSEngineProtocol,
)
from nova.core.logging import get_logger, setup_logging
from nova.core.pipeline import NovaPipeline, PipelineTurnResult
from nova.core.settings import NovaSettings, SettingsManager
from nova.core.state import InvalidStateTransitionError, PipelineState, PipelineStateMachine

__all__ = [
    "ActionID",
    "ActionRequest",
    "ActionResult",
    "AllowlistValidator",
    "ConfirmationHandlerProtocol",
    "FakeConfirmationHandler",
    "FakeIntentEngine",
    "FakePlatformAdapter",
    "FakeSTTEngine",
    "FakeTTSEngine",
    "IntentEngineProtocol",
    "InvalidStateTransitionError",
    "NovaPipeline",
    "NovaSettings",
    "PipelineState",
    "PipelineStateMachine",
    "PipelineTurnResult",
    "PlatformAdapterProtocol",
    "STTEngineProtocol",
    "SettingsManager",
    "TTSEngineProtocol",
    "TranscriptionResult",
    "get_logger",
    "setup_logging",
]
