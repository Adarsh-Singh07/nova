"""Unit tests for NovaSignals Qt signal bridge."""

from __future__ import annotations

from typing import Any

from nova.ui.signals import NovaSignals


def test_signals_emission(qtbot: Any) -> None:
    signals = NovaSignals()

    with qtbot.waitSignal(signals.state_changed, timeout=1000) as blocker:
        signals.state_changed.emit("listening")
    assert blocker.args == ["listening"]

    with qtbot.waitSignal(signals.transcript_updated, timeout=1000) as blocker:
        signals.transcript_updated.emit("open calculator")
    assert blocker.args == ["open calculator"]

    with qtbot.waitSignal(signals.reply_ready, timeout=1000) as blocker:
        signals.reply_ready.emit("Calculator opened.")
    assert blocker.args == ["Calculator opened."]

    with qtbot.waitSignal(signals.error_occurred, timeout=1000) as blocker:
        signals.error_occurred.emit("Device failed")
    assert blocker.args == ["Device failed"]

    with qtbot.waitSignal(signals.turn_finished, timeout=1000):
        signals.turn_finished.emit()
