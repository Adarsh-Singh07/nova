"""Cross-thread Qt signal bridge for NOVA.

All pipeline events are delivered to the UI thread through this QObject.
The pipeline (running in a QThread worker) emits these signals;
the UI (running on the main thread) connects to them. Never call widget
methods directly from the worker thread.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class NovaSignals(QObject):
    """Central Qt signal hub between NovaPipeline and the UI layer."""

    # Pipeline state change — carries the PipelineState string value
    state_changed = Signal(str)

    # Live transcript text as words accumulate
    transcript_updated = Signal(str)

    # NOVA's final spoken reply text
    reply_ready = Signal(str)

    # User-visible error message
    error_occurred = Signal(str)

    # Pipeline finished processing one complete turn
    turn_finished = Signal()

    # Hotkey or wake-word triggered — instruct UI to show bubble
    listening_started = Signal()

    # Signal carrying an action description while ACTING
    action_started = Signal(str)
