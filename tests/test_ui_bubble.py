"""Unit tests for NovaBubble floating status overlay."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt

from nova.ui.bubble import NovaBubble


def test_bubble_initialization_and_text_input(qtbot: Any) -> None:
    submitted_texts: list[str] = []

    def on_submit(text: str) -> None:
        submitted_texts.append(text)

    bubble = NovaBubble(on_text_submit=on_submit)
    qtbot.addWidget(bubble)

    # 1. Check initial state
    assert bubble.windowTitle() == ""
    assert bubble.windowFlags() & Qt.WindowType.FramelessWindowHint

    # 2. State updates
    bubble.set_state("listening")
    assert "Listening" in bubble._state_label.text()

    bubble.set_state("transcribing")
    assert "Transcribing" in bubble._state_label.text()

    # 3. Transcript updates
    bubble.set_transcript("volume up")
    assert bubble._transcript_label.isVisible()
    assert "volume up" in bubble._transcript_label.text()

    # 4. Reply updates
    bubble.set_reply("Volume increased.")
    assert bubble._reply_label.isVisible()
    assert "Volume increased" in bubble._reply_label.text()

    # 5. Text fallback submission (Rule R6)
    bubble._text_input.setText("mute audio")
    bubble._handle_text_submit()
    assert submitted_texts == ["mute audio"]
    assert bubble._text_input.text() == ""

    # 6. Pin toggle
    assert bubble._is_pinned is False
    bubble.toggle_pin()
    assert bubble._is_pinned is True
    assert bubble._pin_btn.isChecked() is True
    bubble.toggle_pin()
    assert bubble._is_pinned is False
    assert bubble._pin_btn.isChecked() is False

    # 7. Show and Hide
    bubble.show_bubble()
    assert bubble.isVisible()
    bubble.hide_bubble()
