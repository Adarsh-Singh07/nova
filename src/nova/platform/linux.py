"""Linux platform adapter implementing audio, media, theme, app, and system actions."""

from __future__ import annotations

import configparser
import glob
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess

import psutil

from nova.core.interfaces import ActionResult
from nova.platform.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class LinuxPlatformAdapter(BasePlatformAdapter):
    """Linux platform adapter supporting PipeWire, PulseAudio, XDG apps, and desktop control."""

    def __init__(self) -> None:
        self._wpctl: str | None = shutil.which("wpctl")
        self._pactl: str | None = shutil.which("pactl")
        self._amixer: str | None = shutil.which("amixer")
        self._playerctl: str | None = shutil.which("playerctl")
        self._gsettings: str | None = shutil.which("gsettings")
        self._plasma_theme: str | None = shutil.which("plasma-apply-lookandfeel")
        self._loginctl: str | None = shutil.which("loginctl")
        self._systemctl: str | None = shutil.which("systemctl")

    def _refresh_binaries(self) -> None:
        """Refresh binary availability at runtime."""
        self._wpctl = shutil.which("wpctl")
        self._pactl = shutil.which("pactl")
        self._amixer = shutil.which("amixer")
        self._playerctl = shutil.which("playerctl")
        self._gsettings = shutil.which("gsettings")
        self._plasma_theme = shutil.which("plasma-apply-lookandfeel")
        self._loginctl = shutil.which("loginctl")
        self._systemctl = shutil.which("systemctl")

    # -------------------------------------------------------------------------
    # Audio Volume & Per-App Control
    # -------------------------------------------------------------------------

    def set_volume(self, percent: int) -> ActionResult:
        """Set master volume percentage via wpctl, pactl, or amixer."""
        self._refresh_binaries()
        clamped = self._clamp_volume(percent)

        # 1. PipeWire / WirePlumber
        if self._wpctl:
            try:
                frac = clamped / 100.0
                subprocess.run(
                    [self._wpctl, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{frac:.2f}"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message=f"Volume set to {clamped}%.",
                    data={"volume": clamped},
                )
            except Exception as e:
                logger.warning("wpctl set-volume failed: %s", e)

        # 2. PulseAudio
        if self._pactl:
            try:
                subprocess.run(
                    [self._pactl, "set-sink-volume", "@DEFAULT_SINK@", f"{clamped}%"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message=f"Volume set to {clamped}%.",
                    data={"volume": clamped},
                )
            except Exception as e:
                logger.warning("pactl set-sink-volume failed: %s", e)

        # 3. ALSA amixer fallback
        if self._amixer:
            try:
                subprocess.run(
                    [self._amixer, "-D", "pulse", "sset", "Master", f"{clamped}%"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message=f"Volume set to {clamped}%.",
                    data={"volume": clamped},
                )
            except Exception as e:
                logger.warning("amixer sset Master failed: %s", e)

        return ActionResult(
            success=False,
            message="No supported Linux audio manager (wpctl, pactl, amixer) found.",
            error="Audio backend unavailable",
        )

    def get_volume(self) -> int:
        """Get current master volume percentage between 0 and 100."""
        self._refresh_binaries()

        # 1. wpctl
        if self._wpctl:
            try:
                res = subprocess.run(
                    [self._wpctl, "get-volume", "@DEFAULT_AUDIO_SINK@"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                match = re.search(r"Volume:\s+([0-9.]+)", res.stdout)
                if match:
                    return round(float(match.group(1)) * 100.0)
            except Exception as e:
                logger.warning("wpctl get-volume failed: %s", e)

        # 2. pactl
        if self._pactl:
            try:
                res = subprocess.run(
                    [self._pactl, "get-sink-volume", "@DEFAULT_SINK@"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                match = re.search(r"(\d+)%", res.stdout)
                if match:
                    return int(match.group(1))
            except Exception as e:
                logger.warning("pactl get-sink-volume failed: %s", e)

        # 3. amixer
        if self._amixer:
            try:
                res = subprocess.run(
                    [self._amixer, "-D", "pulse", "sget", "Master"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                match = re.search(r"\[(\d+)%\]", res.stdout)
                if match:
                    return int(match.group(1))
            except Exception as e:
                logger.warning("amixer sget Master failed: %s", e)

        return 50

    def toggle_mute(self) -> ActionResult:
        """Toggle system audio mute state."""
        self._refresh_binaries()

        if self._wpctl:
            try:
                subprocess.run(
                    [self._wpctl, "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message="Toggled audio mute.")
            except Exception as e:
                logger.warning("wpctl set-mute failed: %s", e)

        if self._pactl:
            try:
                subprocess.run(
                    [self._pactl, "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message="Toggled audio mute.")
            except Exception as e:
                logger.warning("pactl set-sink-mute failed: %s", e)

        if self._amixer:
            try:
                subprocess.run(
                    [self._amixer, "-D", "pulse", "sset", "Master", "toggle"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message="Toggled audio mute.")
            except Exception as e:
                logger.warning("amixer mute toggle failed: %s", e)

        return ActionResult(
            success=False,
            message="No supported Linux audio manager (wpctl, pactl, amixer) found.",
            error="Audio backend unavailable",
        )

    def set_app_volume(self, app_name: str, percent: int) -> ActionResult:
        """Set volume percentage for a specific running application via pactl sink-inputs."""
        clamped = self._clamp_volume(percent)
        self._refresh_binaries()

        if not self._pactl:
            return ActionResult(
                success=False,
                message="Per-app volume requires PulseAudio/PipeWire pactl tool.",
                error="pactl unavailable",
            )

        try:
            # Query active sink inputs
            res = subprocess.run(
                [self._pactl, "list", "sink-inputs"],
                capture_output=True,
                text=True,
                check=False,
            )
            sections = res.stdout.split("Sink Input #")
            target_lower = app_name.lower().strip()
            matched_sink_ids: list[str] = []

            for sec in sections[1:]:
                lines = sec.splitlines()
                sink_id = lines[0].strip()
                sec_lower = sec.lower()
                if f'application.name = "{target_lower}"' in sec_lower or target_lower in sec_lower:
                    matched_sink_ids.append(sink_id)

            if not matched_sink_ids:
                return ActionResult(
                    success=False,
                    message=f"No active audio stream found for '{app_name}'.",
                    error="Stream not found",
                )

            for sid in matched_sink_ids:
                subprocess.run(
                    [self._pactl, "set-sink-input-volume", sid, f"{clamped}%"],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            return ActionResult(
                success=True,
                message=f"Set {app_name} volume to {clamped}%.",
                data={"app_name": app_name, "volume": clamped},
            )

        except Exception as e:
            logger.exception("Error adjusting Linux per-app volume for %s", app_name)
            return ActionResult(
                success=False,
                message=f"Failed to adjust volume for '{app_name}'.",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Media Control
    # -------------------------------------------------------------------------

    def _send_playerctl(self, command: str) -> ActionResult:
        """Dispatch media command via playerctl or D-Bus MPRIS2."""
        self._refresh_binaries()

        if self._playerctl:
            try:
                subprocess.run(
                    [self._playerctl, command],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message=f"Media command '{command}' executed.")
            except Exception as e:
                logger.warning("playerctl %s failed: %s", command, e)

        # Fallback to dbus-send for PlayPause
        dbus_cmd = shutil.which("dbus-send")
        if dbus_cmd and command == "play-pause":
            try:
                subprocess.run(
                    [
                        dbus_cmd,
                        "--type=method_call",
                        "--dest=org.mpris.MediaPlayer2.*",
                        "/org/mpris/MediaPlayer2",
                        "org.mpris.MediaPlayer2.Player.PlayPause",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return ActionResult(success=True, message="Media play/pause dispatched via D-Bus.")
            except Exception as e:
                logger.warning("dbus-send media failed: %s", e)

        return ActionResult(
            success=False,
            message="No media controller (playerctl or dbus-send) found.",
            error="Media controller unavailable",
        )

    def media_play_pause(self) -> ActionResult:
        """Toggle media playback (play/pause)."""
        return self._send_playerctl("play-pause")

    def media_next(self) -> ActionResult:
        """Skip to next media track."""
        return self._send_playerctl("next")

    def media_previous(self) -> ActionResult:
        """Return to previous media track."""
        return self._send_playerctl("previous")

    def media_stop(self) -> ActionResult:
        """Stop active media playback."""
        return self._send_playerctl("stop")

    # -------------------------------------------------------------------------
    # Desktop Theme Support (GNOME & KDE Plasma)
    # -------------------------------------------------------------------------

    def toggle_dark_mode(self) -> ActionResult:
        """Toggle dark/light desktop theme in GNOME or KDE Plasma environments."""
        self._refresh_binaries()
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

        # 1. GNOME / Unity environments
        if self._gsettings and ("gnome" in desktop or "unity" in desktop or not desktop):
            try:
                res = subprocess.run(
                    [self._gsettings, "get", "org.gnome.desktop.interface", "color-scheme"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                is_dark = "prefer-dark" in res.stdout
                new_scheme = "default" if is_dark else "prefer-dark"
                theme_str = "light" if is_dark else "dark"

                subprocess.run(
                    [
                        self._gsettings,
                        "set",
                        "org.gnome.desktop.interface",
                        "color-scheme",
                        new_scheme,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message=f"Switched to {theme_str} theme.",
                    data={"theme": theme_str},
                )
            except Exception as e:
                logger.warning("gsettings theme toggle failed: %s", e)

        # 2. KDE Plasma environment
        if self._plasma_theme and ("kde" in desktop or "plasma" in desktop):
            try:
                # Apply Breeze Dark
                subprocess.run(
                    [self._plasma_theme, "-a", "org.kde.breezedark.desktop"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message="Switched to dark theme on KDE Plasma.",
                    data={"theme": "dark"},
                )
            except Exception as e:
                logger.warning("plasma-apply-lookandfeel failed: %s", e)

        return ActionResult(
            success=False,
            message="Desktop theme switching is supported on GNOME and KDE Plasma environments.",
            error="Unsupported desktop environment",
        )

    # -------------------------------------------------------------------------
    # Application Discovery & Launching
    # -------------------------------------------------------------------------

    def _find_desktop_entry(self, app_name: str) -> list[str] | None:
        """Discover an application's executable from standard XDG .desktop files."""
        clean_name = app_name.strip().lower()
        search_dirs = [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications"),
        ]

        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            for file_path in glob.glob(os.path.join(d, "*.desktop")):
                try:
                    config = configparser.ConfigParser(interpolation=None)
                    config.read(file_path, encoding="utf-8")
                    if not config.has_section("Desktop Entry"):
                        continue
                    section = config["Desktop Entry"]
                    name = section.get("Name", "").strip().lower()
                    generic_name = section.get("GenericName", "").strip().lower()
                    exec_cmd = section.get("Exec", "").strip()

                    if (
                        clean_name in (name, generic_name)
                        or clean_name in os.path.basename(file_path).lower()
                    ) and exec_cmd:
                        # Strip XDG field codes (%f, %u, %F, %U, etc.)
                        cleaned_exec = re.sub(r"%\w+", "", exec_cmd).strip()
                        parts = shlex.split(cleaned_exec)
                        if parts and shutil.which(parts[0]):
                            return parts
                except Exception:
                    continue

        # Check if direct binary exists on PATH
        binary = shutil.which(clean_name)
        if binary:
            return [binary]

        return None

    def launch_app(self, app_name_or_target: str) -> ActionResult:
        """Launch an application directly using subprocess without a shell."""
        cmd_parts = self._find_desktop_entry(app_name_or_target)
        if not cmd_parts:
            return ActionResult(
                success=False,
                message=f"Could not find application '{app_name_or_target}'.",
                error="Application not found",
            )

        try:
            # Strictly non-shell execution
            subprocess.Popen(
                cmd_parts,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                shell=False,
            )
            return ActionResult(
                success=True,
                message=f"Launched {app_name_or_target}.",
                data={"target": cmd_parts[0]},
            )
        except Exception as e:
            logger.exception("Failed to launch Linux application: %s", cmd_parts)
            return ActionResult(
                success=False,
                message=f"Failed to launch '{app_name_or_target}'.",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Application Closing & Process Deny-List
    # -------------------------------------------------------------------------

    def close_app(self, app_name_or_target: str) -> ActionResult:
        """Gracefully close an application process using SIGTERM with SIGKILL fallback."""
        clean_target = app_name_or_target.strip()
        if self.is_critical_process(clean_target):
            return ActionResult(
                success=False,
                message=f"Refused to terminate protected system process: '{clean_target}'.",
                error="Critical process protection",
            )

        target_lower = clean_target.lower()
        target_stem, _ = os.path.splitext(target_lower)
        matched_procs: list[psutil.Process] = []

        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    p_name = proc.info["name"]
                    if not p_name:
                        continue
                    p_lower = p_name.lower()
                    p_stem, _ = os.path.splitext(p_lower)
                    if (
                        target_lower == p_lower or target_stem == p_stem
                    ) and not self.is_critical_process(p_name):
                        matched_procs.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning("Error enumerating processes for close: %s", e)

        if not matched_procs:
            return ActionResult(
                success=False,
                message=f"No running process found for '{clean_target}'.",
                error="Process not running",
            )

        closed_count = 0
        for proc in matched_procs:
            try:
                # Step 1: Graceful SIGTERM
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=1.5)
                    closed_count += 1
                    continue
                except psutil.TimeoutExpired:
                    pass

                # Step 2: Force SIGKILL fallback
                sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
                proc.send_signal(sigkill)
                proc.wait(timeout=1.0)
                closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                closed_count += 1

        return ActionResult(
            success=True,
            message=f"Closed {clean_target}.",
            data={"target": clean_target, "instances_closed": closed_count},
        )

    # -------------------------------------------------------------------------
    # System Session Control
    # -------------------------------------------------------------------------

    def lock_workstation(self) -> ActionResult:
        """Lock the Linux user session via loginctl or D-Bus screensaver."""
        self._refresh_binaries()

        # 1. loginctl lock-session
        if self._loginctl:
            try:
                subprocess.run(
                    [self._loginctl, "lock-session"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message="Workstation locked.")
            except Exception as e:
                logger.warning("loginctl lock-session failed: %s", e)

        # 2. xdg-screensaver lock
        xdg_ss = shutil.which("xdg-screensaver")
        if xdg_ss:
            try:
                subprocess.run(
                    [xdg_ss, "lock"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message="Workstation locked.")
            except Exception as e:
                logger.warning("xdg-screensaver lock failed: %s", e)

        # 3. D-Bus org.freedesktop.ScreenSaver.Lock
        dbus_cmd = shutil.which("dbus-send")
        if dbus_cmd:
            try:
                subprocess.run(
                    [
                        dbus_cmd,
                        "--type=method_call",
                        "--dest=org.freedesktop.ScreenSaver",
                        "/ScreenSaver",
                        "org.freedesktop.ScreenSaver.Lock",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return ActionResult(success=True, message="Workstation locked via D-Bus.")
            except Exception as e:
                logger.warning("dbus-send ScreenSaver lock failed: %s", e)

        return ActionResult(
            success=False,
            message="No screen lock mechanism (loginctl, xdg-screensaver, or dbus) found.",
            error="Lock utility unavailable",
        )

    def suspend_system(self) -> ActionResult:
        """Suspend the Linux computer via systemctl or loginctl."""
        self._refresh_binaries()

        if self._systemctl:
            try:
                subprocess.run(
                    [self._systemctl, "suspend"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message="System entering sleep mode.")
            except Exception as e:
                logger.warning("systemctl suspend failed: %s", e)

        if self._loginctl:
            try:
                subprocess.run(
                    [self._loginctl, "suspend"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(success=True, message="System entering sleep mode.")
            except Exception as e:
                logger.warning("loginctl suspend failed: %s", e)

        return ActionResult(
            success=False,
            message="No system suspend utility (systemctl or loginctl) found.",
            error="Suspend utility unavailable",
        )

    # -------------------------------------------------------------------------
    # Virtual Keyboard Input Control
    # -------------------------------------------------------------------------

    def type_text(self, text: str) -> ActionResult:
        """Type text into active window via xdotool or ydotool."""
        xdotool = shutil.which("xdotool")
        ydotool = shutil.which("ydotool")

        if xdotool:
            try:
                subprocess.run(
                    [xdotool, "type", "--", text],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message="Typed text into active window.",
                    data={"length": len(text)},
                )
            except Exception as e:
                logger.warning("xdotool type failed: %s", e)
                return ActionResult(
                    success=False,
                    message="Failed to type text via xdotool.",
                    error=str(e),
                )

        if ydotool:
            try:
                subprocess.run(
                    [ydotool, "type", "--", text],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message="Typed text into active window.",
                    data={"length": len(text)},
                )
            except Exception as e:
                logger.warning("ydotool type failed: %s", e)
                return ActionResult(
                    success=False,
                    message="Failed to type text via ydotool.",
                    error=str(e),
                )

        return ActionResult(
            success=False,
            message="No typing utility (xdotool or ydotool) found.",
            error="xdotool/ydotool unavailable",
        )

    def press_key(self, key: str) -> ActionResult:
        """Press a virtual key in active window via xdotool or ydotool."""
        clean_key = key.strip().lower()
        key_name = "Return" if clean_key in ("enter", "return") else clean_key.capitalize()
        xdotool = shutil.which("xdotool")
        ydotool = shutil.which("ydotool")

        if xdotool:
            try:
                subprocess.run(
                    [xdotool, "key", key_name],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message=f"Pressed {clean_key} key.",
                    data={"key": clean_key},
                )
            except Exception as e:
                logger.warning("xdotool key failed: %s", e)
                return ActionResult(
                    success=False,
                    message=f"Failed to press key {clean_key}.",
                    error=str(e),
                )

        if ydotool:
            try:
                subprocess.run(
                    [ydotool, "key", clean_key],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return ActionResult(
                    success=True,
                    message=f"Pressed {clean_key} key.",
                    data={"key": clean_key},
                )
            except Exception as e:
                logger.warning("ydotool key failed: %s", e)
                return ActionResult(
                    success=False,
                    message=f"Failed to press key {clean_key}.",
                    error=str(e),
                )

        return ActionResult(
            success=False,
            message="No keypress utility (xdotool or ydotool) found.",
            error="xdotool/ydotool unavailable",
        )
