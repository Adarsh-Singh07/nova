"""NOVA floating transcript/status bubble.

A borderless, always-on-top, translucent overlay that appears in the
bottom-left corner of the primary screen when NOVA is active.

Layout (top → bottom):
  ┌─────────────────────────────────────┐
  │ 🎙 LISTENING…                 [✕]  │
  │ "set volume to forty percent"       │
  │ ▶ Setting volume to 40%             │
  │ ─────────────────────────────────── │
  │ [ Type a command…              ↵ ]  │
  └─────────────────────────────────────┘
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nova.ui.theme import bubble_stylesheet

logger = logging.getLogger(__name__)

# Gap (px) between bubble and the bottom/left of screen edge
_MARGIN_X = 16
_MARGIN_Y = 72  # clear of taskbar (typically 40-48 px high + some breathing room)
_BUBBLE_WIDTH = 320


class NovaBubble(QWidget):
    """Floating, always-on-top status and transcript bubble.

    Shown in bottom-left of the primary screen; slides up when visible
    and fades out when idle.
    """

    def __init__(self, on_text_submit: Callable[[str], None] | None = None) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._on_text_submit = on_text_submit
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.hide_bubble)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(0.0)
        self.setFixedWidth(_BUBBLE_WIDTH)

        self._build_ui()
        self._slide_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_anim.setDuration(220)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(180)

    # ─── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._frame = QFrame(self)
        self._frame.setObjectName("NovaBubble")
        outer.addWidget(self._frame)

        inner = QVBoxLayout(self._frame)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(6)

        # ── Header row: state label + close button ──
        header = QHBoxLayout()
        self._state_label = QLabel("NOVA", self._frame)
        self._state_label.setObjectName("StateLabel")
        header.addWidget(self._state_label)
        header.addStretch()

        close_btn = QPushButton("✕", self._frame)
        close_btn.setFixedSize(18, 18)
        close_btn.setFlat(True)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide_bubble)
        close_btn.setToolTip("Dismiss")
        header.addWidget(close_btn)
        inner.addLayout(header)

        # ── Transcript label ──
        self._transcript_label = QLabel("", self._frame)
        self._transcript_label.setObjectName("TranscriptLabel")
        self._transcript_label.setWordWrap(True)
        self._transcript_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._transcript_label.setVisible(False)
        inner.addWidget(self._transcript_label)

        # ── Reply label ──
        self._reply_label = QLabel("", self._frame)
        self._reply_label.setObjectName("ReplyLabel")
        self._reply_label.setWordWrap(True)
        self._reply_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._reply_label.setVisible(False)
        inner.addWidget(self._reply_label)

        # ── Divider ──
        divider = QFrame(self._frame)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        inner.addWidget(divider)

        # ── Text fallback input (Rule R6: always accessible) ──
        self._text_input = QLineEdit(self._frame)
        self._text_input.setObjectName("TextFallback")
        self._text_input.setPlaceholderText("Type a command…")
        self._text_input.returnPressed.connect(self._handle_text_submit)
        self._text_input.setToolTip("Type a command and press Enter (keyboard fallback for voice)")
        inner.addWidget(self._text_input)

        self._apply_theme()

    def _apply_theme(self) -> None:
        self._frame.setStyleSheet(bubble_stylesheet())

    # ─── Public API (called from UI thread via signals) ──────────────────────

    def set_state(self, state: str) -> None:
        """Update the state label text and auto-show the bubble."""
        label_map = {
            "idle": "NOVA · Idle",
            "listening": "🎙 Listening…",
            "transcribing": "⌛ Transcribing…",
            "thinking": "💭 Thinking…",
            "awaiting_confirmation": "⚠ Awaiting confirmation…",
            "acting": "⚡ Executing…",
            "speaking": "🔊 Speaking…",
            "error": "❌ Error",
        }
        self._state_label.setText(label_map.get(state, state.upper()))
        self._auto_hide_timer.stop()
        if state == "idle":
            self._schedule_hide(delay_ms=1500)
        else:
            self.show_bubble()

    def set_transcript(self, text: str) -> None:
        """Update live transcript text."""
        self._transcript_label.setText(f'"{text}"')
        self._transcript_label.setVisible(bool(text))
        self._reply_label.setVisible(False)
        self._adjust_height()

    def set_reply(self, text: str) -> None:
        """Show NOVA's spoken reply text."""
        self._reply_label.setText(f"▶ {text}")
        self._reply_label.setVisible(bool(text))
        self._adjust_height()

    def clear(self) -> None:
        """Clear transcript and reply content."""
        self._transcript_label.setText("")
        self._transcript_label.setVisible(False)
        self._reply_label.setText("")
        self._reply_label.setVisible(False)
        self._adjust_height()

    def show_bubble(self) -> None:
        """Slide the bubble in from the bottom-left."""
        self._auto_hide_timer.stop()
        self._position_bubble()
        self.show()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def hide_bubble(self) -> None:
        """Fade the bubble out and then hide it."""
        self._auto_hide_timer.stop()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_fade_out_done)
        self._fade_anim.start()

    # ─── Private helpers ─────────────────────────────────────────────────────

    def _schedule_hide(self, delay_ms: int = 2500) -> None:
        self._auto_hide_timer.start(delay_ms)

    def _on_fade_out_done(self) -> None:
        self.hide()
        self.clear()
        with contextlib.suppress(RuntimeError):
            self._fade_anim.finished.disconnect(self._on_fade_out_done)

    def _position_bubble(self) -> None:
        """Position the bubble at the bottom-left of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available: QRect = screen.availableGeometry()
        self.adjustSize()
        h = self.sizeHint().height()
        x = available.left() + _MARGIN_X
        y = available.bottom() - h - _MARGIN_Y
        self.move(QPoint(x, y))

    def _adjust_height(self) -> None:
        """Resize the window after content changes and re-position."""
        self.adjustSize()
        self._position_bubble()

    def _handle_text_submit(self) -> None:
        text = self._text_input.text().strip()
        self._text_input.clear()
        if not text:
            return
        if self._on_text_submit is not None:
            self._on_text_submit(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bubble()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click anywhere on the bubble to dismiss it."""
        self.hide_bubble()
