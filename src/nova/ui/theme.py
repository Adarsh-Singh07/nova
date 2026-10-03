"""High-contrast-safe color palette and dark/light theme helpers for NOVA UI.

Rule R6: UI must be accessible with high-contrast-safe colours.
Semantic color tokens (not hardcoded hex) are used throughout so that
the palette can be swapped without touching widget code.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _is_dark_mode() -> bool:
    """Detect whether the host OS is currently using dark mode.

    Uses Qt palette luminance heuristic — works cross-platform without
    reading the Windows registry or GNOME gsettings directly.
    """
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return True  # safe default
    palette = app.palette()
    window_color: QColor = palette.color(QPalette.ColorRole.Window)
    # If the window background luminance is below 128 the OS is in dark mode
    return window_color.lightness() < 128


class Palette:
    """Semantic color tokens that adapt to the current OS theme."""

    # Bubble background
    BUBBLE_BG_DARK = QColor(30, 30, 30, 230)  # semi-transparent dark
    BUBBLE_BG_LIGHT = QColor(245, 245, 245, 230)  # semi-transparent light

    # Primary text
    TEXT_PRIMARY_DARK = QColor(240, 240, 240)
    TEXT_PRIMARY_LIGHT = QColor(20, 20, 20)

    # Secondary / hint text
    TEXT_SECONDARY_DARK = QColor(160, 160, 160)
    TEXT_SECONDARY_LIGHT = QColor(100, 100, 100)

    # Accent (NOVA brand — a deep indigo)
    ACCENT = QColor(99, 102, 241)  # #6366F1
    ACCENT_HOVER = QColor(79, 70, 229)  # #4F46E5

    # Error / destructive
    DANGER = QColor(239, 68, 68)  # #EF4444

    # Success
    SUCCESS = QColor(16, 185, 129)  # #10B981

    # Input fallback border
    INPUT_BORDER_DARK = QColor(70, 70, 70)
    INPUT_BORDER_LIGHT = QColor(200, 200, 200)

    @classmethod
    def bubble_bg(cls) -> QColor:
        return cls.BUBBLE_BG_DARK if _is_dark_mode() else cls.BUBBLE_BG_LIGHT

    @classmethod
    def text_primary(cls) -> QColor:
        return cls.TEXT_PRIMARY_DARK if _is_dark_mode() else cls.TEXT_PRIMARY_LIGHT

    @classmethod
    def text_secondary(cls) -> QColor:
        return cls.TEXT_SECONDARY_DARK if _is_dark_mode() else cls.TEXT_SECONDARY_LIGHT

    @classmethod
    def input_border(cls) -> QColor:
        return cls.INPUT_BORDER_DARK if _is_dark_mode() else cls.INPUT_BORDER_LIGHT


BUBBLE_STYLESHEET_DARK = """
    QFrame#NovaBubble {
        background-color: rgba(30, 30, 30, 230);
        border-radius: 12px;
        border: 1px solid rgba(99, 102, 241, 180);
    }
    QLabel#StateLabel {
        color: #A5B4FC;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    QLabel#TranscriptLabel {
        color: #F0F0F0;
        font-size: 14px;
    }
    QLabel#ReplyLabel {
        color: #D1FAE5;
        font-size: 13px;
        font-style: italic;
    }
    QLineEdit#TextFallback {
        background-color: rgba(50, 50, 50, 200);
        border: 1px solid rgba(99, 102, 241, 150);
        border-radius: 6px;
        color: #F0F0F0;
        font-size: 13px;
        padding: 4px 8px;
        selection-background-color: #6366F1;
    }
    QLineEdit#TextFallback:focus {
        border-color: #6366F1;
    }
"""

BUBBLE_STYLESHEET_LIGHT = """
    QFrame#NovaBubble {
        background-color: rgba(245, 245, 245, 230);
        border-radius: 12px;
        border: 1px solid rgba(99, 102, 241, 180);
    }
    QLabel#StateLabel {
        color: #4338CA;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    QLabel#TranscriptLabel {
        color: #1A1A1A;
        font-size: 14px;
    }
    QLabel#ReplyLabel {
        color: #065F46;
        font-size: 13px;
        font-style: italic;
    }
    QLineEdit#TextFallback {
        background-color: rgba(255, 255, 255, 200);
        border: 1px solid rgba(99, 102, 241, 150);
        border-radius: 6px;
        color: #1A1A1A;
        font-size: 13px;
        padding: 4px 8px;
    }
    QLineEdit#TextFallback:focus {
        border-color: #6366F1;
    }
"""


def bubble_stylesheet() -> str:
    """Return the appropriate bubble stylesheet for current OS theme."""
    return BUBBLE_STYLESHEET_DARK if _is_dark_mode() else BUBBLE_STYLESHEET_LIGHT


SETTINGS_STYLESHEET = """
    QDialog {
        background-color: #1E1E2E;
        color: #CDD6F4;
        font-size: 13px;
    }
    QWidget {
        color: #CDD6F4;
    }
    QTabWidget::pane {
        border: 1px solid #45475A;
        border-radius: 6px;
        background-color: #181825;
    }
    QTabBar::tab {
        background-color: #1E1E2E;
        color: #A6ADC8;
        padding: 8px 16px;
        min-width: 80px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background-color: #313244;
        color: #6366F1;
        font-weight: 600;
        border-bottom: 2px solid #6366F1;
    }
    QGroupBox {
        color: #CBA6F7;
        font-weight: bold;
        border: 1px solid #45475A;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 14px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
    }
    QLineEdit, QComboBox {
        background-color: #313244;
        border: 1px solid #45475A;
        border-radius: 6px;
        color: #CDD6F4;
        padding: 6px 10px;
    }
    QPushButton {
        background-color: #313244;
        color: #CDD6F4;
        border: 1px solid #45475A;
        padding: 6px 16px;
        border-radius: 6px;
    }
    QPushButton:hover {
        background-color: #45475A;
    }
    QPushButton[role="primary"] {
        background-color: #6366F1;
        color: white;
        border: none;
    }
    QPushButton[role="primary"]:hover {
        background-color: #4F46E5;
    }
    QPushButton[role="danger"] {
        color: #EF4444;
    }
"""

WIZARD_STYLESHEET = """
    QWizard {
        background-color: #181825;
        color: #CDD6F4;
        font-family: 'Segoe UI', sans-serif;
    }
    QWizardPage {
        background-color: #181825;
        color: #CDD6F4;
    }
    QWidget {
        background-color: #181825;
        color: #CDD6F4;
    }
    QLabel {
        color: #CDD6F4;
        font-size: 13px;
        background-color: transparent;
    }
    QLineEdit, QComboBox {
        background-color: #313244;
        border: 1px solid #45475A;
        border-radius: 6px;
        color: #CDD6F4;
        padding: 6px 10px;
    }
    QComboBox QAbstractItemView {
        background-color: #313244;
        color: #CDD6F4;
        selection-background-color: #6366F1;
    }
    QCheckBox {
        color: #CDD6F4;
        font-size: 13px;
        spacing: 8px;
        background-color: transparent;
    }
    QPushButton {
        background-color: #6366F1;
        color: white;
        border-radius: 6px;
        padding: 7px 18px;
        font-weight: 600;
        border: none;
    }
    QPushButton:hover {
        background-color: #4F46E5;
    }
    QPushButton:disabled {
        background-color: #313244;
        color: #6C7086;
    }
    QProgressBar {
        background-color: #313244;
        border: 1px solid #45475A;
        border-radius: 6px;
        text-align: center;
        color: #CDD6F4;
        height: 18px;
    }
    QProgressBar::chunk {
        background-color: #10B981;
        border-radius: 5px;
    }
"""


def apply_platform_theme(app: QApplication) -> None:
    """Apply consistent font and DPI-aware settings to the application."""
    if sys.platform == "win32":
        # Use Segoe UI on Windows for native feel
        from PySide6.QtGui import QFont

        font = QFont("Segoe UI", 10)
        app.setFont(font)
    app.setStyleSheet("")  # let OS palette drive global colors; widget-level CSS handles the rest
