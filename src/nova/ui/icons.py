"""Programmatic state-aware icon renderer for NOVA.

Generates QIcon objects on the fly from colored SVG circles —
no external image files required. Each pipeline state gets a
distinct color that is readable on both light and dark taskbars.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Semantic color map: FSM state → hex fill color
_STATE_COLORS: dict[str, str] = {
    "idle": "#6B7280",  # grey
    "listening": "#EF4444",  # red
    "transcribing": "#F59E0B",  # amber
    "thinking": "#3B82F6",  # blue
    "awaiting_confirmation": "#8B5CF6",  # violet
    "acting": "#8B5CF6",  # purple
    "speaking": "#10B981",  # green
    "error": "#DC2626",  # deep red
}

_DEFAULT_COLOR = "#6B7280"
_ICON_SIZE = 64


def _make_svg(color: str) -> bytes:
    """Generate a minimal filled-circle SVG string for a given hex color."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<circle cx="32" cy="32" r="28" fill="{color}"/>'
        f'<text x="32" y="42" font-size="28" text-anchor="middle" '
        f'font-family="sans-serif" fill="white" font-weight="bold">N</text>'
        f"</svg>"
    ).encode()


def _svg_to_icon(svg_bytes: bytes, size: int = _ICON_SIZE) -> QIcon:
    """Render raw SVG bytes to a QIcon of the given pixel size."""
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def icon_for_state(state: str) -> QIcon:
    """Return a state-colored QIcon for the given pipeline state string."""
    color = _STATE_COLORS.get(state, _DEFAULT_COLOR)
    return _svg_to_icon(_make_svg(color))


# Pre-render all state icons once at import time for zero-latency transitions
_ICON_CACHE: dict[str, QIcon] = {}


def get_icon(state: str) -> QIcon:
    """Return a cached QIcon for the given pipeline state.

    The cache is populated lazily on first call per state.
    A QApplication must exist before this is called.
    """
    if state not in _ICON_CACHE:
        _ICON_CACHE[state] = icon_for_state(state)
    return _ICON_CACHE[state]


def clear_icon_cache() -> None:
    """Clear the icon cache (e.g. after theme change)."""
    _ICON_CACHE.clear()
