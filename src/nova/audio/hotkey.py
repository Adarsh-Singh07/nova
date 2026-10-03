"""Cross-platform push-to-talk hotkey listener.

Provides responsive, non-blocking key state monitoring for push-to-talk activation
(default Right Ctrl).
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Windows Virtual Key Codes
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3


class HotkeyListener:
    """Thread-safe background listener monitoring push-to-talk key transitions."""

    def __init__(
        self,
        hotkey_name: str = "ctrl_r",
        on_press: Callable[[], None] | None = None,
        on_release: Callable[[], None] | None = None,
        poll_interval_seconds: float = 0.015,  # 15ms responsive loop (~0.01% CPU)
    ) -> None:
        self.hotkey_name = hotkey_name.lower()
        self.on_press = on_press
        self.on_release = on_release
        self.poll_interval = poll_interval_seconds

        self._is_pressed = False
        self._is_running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_pressed(self) -> bool:
        return self._is_pressed

    def _is_key_down_windows(self) -> bool:
        """Poll key state using native Windows GetAsyncKeyState."""
        try:
            import ctypes

            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return False
            vk = VK_RCONTROL if "r" in self.hotkey_name else VK_CONTROL
            state = windll.user32.GetAsyncKeyState(vk)
            # Most significant bit indicates whether key is currently pressed
            return bool(state & 0x8000)
        except Exception:
            return False

    def _poll_loop(self) -> None:
        """Background thread polling key state."""
        while not self._stop_event.is_set():
            if sys.platform == "win32":
                current_down = self._is_key_down_windows()
            else:
                # On non-Windows platforms, fallback / simulated
                current_down = self._is_pressed

            if current_down and not self._is_pressed:
                self._is_pressed = True
                logger.debug("Push-to-talk hotkey PRESSED.")
                if self.on_press:
                    try:
                        self.on_press()
                    except Exception:
                        logger.exception("Error in hotkey on_press callback")

            elif not current_down and self._is_pressed:
                self._is_pressed = False
                logger.debug("Push-to-talk hotkey RELEASED.")
                if self.on_release:
                    try:
                        self.on_release()
                    except Exception:
                        logger.exception("Error in hotkey on_release callback")

            time.sleep(self.poll_interval)

    def start(self) -> None:
        """Start monitoring hotkey state in a daemon thread."""
        if self._is_running:
            return

        self._is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="NovaHotkeyListener",
            daemon=True,
        )
        self._thread.start()
        logger.info("Hotkey listener active for key '%s'", self.hotkey_name)

    def stop(self) -> None:
        """Stop hotkey monitoring thread."""
        self._is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
        self._is_pressed = False

    def simulate_press(self) -> None:
        """Simulate hotkey press (for testing)."""
        if not self._is_pressed:
            self._is_pressed = True
            if self.on_press:
                self.on_press()

    def simulate_release(self) -> None:
        """Simulate hotkey release (for testing)."""
        if self._is_pressed:
            self._is_pressed = False
            if self.on_release:
                self.on_release()
