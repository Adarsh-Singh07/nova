"""Base platform adapter providing shared interfaces, process allowlists, and helpers."""

from __future__ import annotations

import abc
import logging
import os
import webbrowser

from nova.core.interfaces import ActionResult, PlatformAdapterProtocol

logger = logging.getLogger(__name__)

# Processes that must NEVER be terminated by NOVA
CRITICAL_PROCESS_NAMES: frozenset[str] = frozenset(
    {
        # Windows system essentials
        "system",
        "idle",
        "csrss.exe",
        "lsass.exe",
        "services.exe",
        "smss.exe",
        "svchost.exe",
        "explorer.exe",
        "wininit.exe",
        "winlogon.exe",
        "nova.exe",
        "python.exe",
        "pythonw.exe",
        # Linux system essentials
        "systemd",
        "init",
        "kthreadd",
        "dbus-daemon",
        "xorg",
        "xwayland",
        "wayland",
        "gnome-shell",
        "kwin",
        "pipewire",
        "wireplumber",
        "pulseaudio",
        "python3",
        "nova",
    }
)


class BasePlatformAdapter(abc.ABC, PlatformAdapterProtocol):
    """Abstract base class for platform-specific operating system adapters."""

    def is_critical_process(self, process_name: str) -> bool:
        """Check if a process name or binary path is protected from termination."""
        clean_name = os.path.basename(process_name).strip().lower()
        if clean_name in CRITICAL_PROCESS_NAMES:
            return True
        # Check without .exe extension as well
        name_no_ext, _ = os.path.splitext(clean_name)
        return (
            name_no_ext in CRITICAL_PROCESS_NAMES or f"{name_no_ext}.exe" in CRITICAL_PROCESS_NAMES
        )

    def _clamp_volume(self, percent: int) -> int:
        """Clamp volume percentage to valid [0, 100] range."""
        return max(0, min(100, percent))

    def open_url(self, url: str) -> ActionResult:
        """Open a validated URL in the user's default browser."""
        clean_url = url.strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
            return ActionResult(
                success=False,
                message=f"Refused to open invalid URL protocol: '{clean_url}'",
                error="Invalid URL protocol",
            )

        try:
            opened = webbrowser.open(clean_url)
            if opened:
                return ActionResult(
                    success=True,
                    message=f"Opened {clean_url} in browser.",
                    data={"url": clean_url},
                )
            return ActionResult(
                success=False,
                message="Browser launch returned false.",
                error="Failed to open browser",
            )
        except Exception as e:
            logger.exception("Failed to open URL in default browser: %s", clean_url)
            return ActionResult(
                success=False,
                message="Failed to open web browser.",
                error=str(e),
            )

    @abc.abstractmethod
    def set_volume(self, percent: int) -> ActionResult:
        """Set master system volume to a percentage between 0 and 100."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_volume(self) -> int:
        """Get current master volume percentage between 0 and 100."""
        raise NotImplementedError

    @abc.abstractmethod
    def toggle_mute(self) -> ActionResult:
        """Toggle system audio mute state."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_app_volume(self, app_name: str, percent: int) -> ActionResult:
        """Set volume percentage for a specific running application session."""
        raise NotImplementedError

    @abc.abstractmethod
    def media_play_pause(self) -> ActionResult:
        """Toggle media playback (play/pause)."""
        raise NotImplementedError

    @abc.abstractmethod
    def media_next(self) -> ActionResult:
        """Skip to next media track."""
        raise NotImplementedError

    @abc.abstractmethod
    def media_previous(self) -> ActionResult:
        """Return to previous media track."""
        raise NotImplementedError

    @abc.abstractmethod
    def media_stop(self) -> ActionResult:
        """Stop active media playback."""
        raise NotImplementedError

    @abc.abstractmethod
    def lock_workstation(self) -> ActionResult:
        """Lock the operating system user session."""
        raise NotImplementedError

    @abc.abstractmethod
    def suspend_system(self) -> ActionResult:
        """Put computer into suspend / sleep mode."""
        raise NotImplementedError

    @abc.abstractmethod
    def launch_app(self, app_name_or_target: str) -> ActionResult:
        """Launch an application by registered name, executable, or shortcut."""
        raise NotImplementedError

    @abc.abstractmethod
    def close_app(self, app_name_or_target: str) -> ActionResult:
        """Gracefully close a running application process."""
        raise NotImplementedError

    @abc.abstractmethod
    def toggle_dark_mode(self) -> ActionResult:
        """Toggle system dark/light theme."""
        raise NotImplementedError

    @abc.abstractmethod
    def type_text(self, text: str) -> ActionResult:
        """Type text into the currently active window."""
        raise NotImplementedError

    @abc.abstractmethod
    def press_key(self, key: str) -> ActionResult:
        """Simulate a single virtual key press in the active window."""
        raise NotImplementedError

    def unmute_current_process(self) -> None:
        """Ensure current process audio session is unmuted. Default is a no-op."""
        pass
