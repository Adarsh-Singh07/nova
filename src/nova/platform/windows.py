"""Windows platform adapter implementing audio, media, theme, app, and system actions."""

from __future__ import annotations

import ctypes
import glob
import logging
import os
import sys
from ctypes import wintypes
from typing import Any

import psutil

from nova.core.interfaces import ActionResult
from nova.platform.base import BasePlatformAdapter

logger = logging.getLogger(__name__)

# Safe imports for Windows-specific libraries
if sys.platform == "win32":
    import winreg

    from pycaw.pycaw import AudioUtilities
else:
    winreg = None
    AudioUtilities = None

# Win32 SendInput data structures
PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class Input_I(ctypes.Union):
    _fields_ = [
        ("ki", KeyBdInput),
        ("mi", MouseInput),
        ("hi", HardwareInput),
    ]


class Input(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("ii", Input_I),
    ]


# Virtual Key Codes
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_DELETE = 0x2E

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

WIN_KEY_MAP: dict[str, int] = {
    "enter": VK_RETURN,
    "return": VK_RETURN,
    "tab": VK_TAB,
    "space": VK_SPACE,
    "escape": VK_ESCAPE,
    "esc": VK_ESCAPE,
    "backspace": VK_BACK,
    "delete": VK_DELETE,
    "up": VK_UP,
    "down": VK_DOWN,
    "left": VK_LEFT,
    "right": VK_RIGHT,
    "home": VK_HOME,
    "end": VK_END,
    "pageup": VK_PRIOR,
    "pagedown": VK_NEXT,
}

# Windows Messages
WM_CLOSE = 0x0010
WM_SETTINGCHANGE = 0x001A
WM_APPCOMMAND = 0x0319
HWND_BROADCAST = 0xFFFF
SMTO_ABORTIFHUNG = 0x0002

APPCOMMAND_MEDIA_NEXTTRACK = 11
APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
APPCOMMAND_MEDIA_STOP = 13
APPCOMMAND_MEDIA_PLAY_PAUSE = 14


class WindowsPlatformAdapter(BasePlatformAdapter):
    """Windows 10/11 platform adapter using pycaw, Win32 APIs, and safe Shell execution."""

    def __init__(self) -> None:
        self._windll: Any = getattr(ctypes, "windll", None)

    # -------------------------------------------------------------------------
    # Audio Volume & Per-App Control
    # -------------------------------------------------------------------------

    def _get_endpoint_volume(self) -> Any:
        """Retrieve the primary audio endpoint volume interface via pycaw."""
        if AudioUtilities is None:
            logger.warning("pycaw is not available on this platform.")
            return None

        try:
            speakers = AudioUtilities.GetSpeakers()
            if speakers is None:
                return None
            return getattr(speakers, "EndpointVolume", None)
        except Exception as e:
            logger.warning("Failed to access Windows audio endpoint: %s", e)
            return None

    def set_volume(self, percent: int) -> ActionResult:
        """Set master system volume to a percentage between 0 and 100."""
        clamped = self._clamp_volume(percent)
        endpoint = self._get_endpoint_volume()
        if endpoint is None:
            return ActionResult(
                success=False,
                message="No active audio output endpoint detected.",
                error="Audio device unavailable",
            )

        try:
            scalar = clamped / 100.0
            endpoint.SetMasterVolumeLevelScalar(scalar, None)
            return ActionResult(
                success=True,
                message=f"Volume set to {clamped}%.",
                data={"volume": clamped},
            )
        except Exception as e:
            logger.exception("Error setting Windows master volume")
            return ActionResult(
                success=False,
                message="Failed to adjust volume.",
                error=str(e),
            )

    def get_volume(self) -> int:
        """Get current master volume percentage between 0 and 100."""
        endpoint = self._get_endpoint_volume()
        if endpoint is None:
            return 50  # Safe fallback default

        try:
            scalar = float(endpoint.GetMasterVolumeLevelScalar())
            return round(scalar * 100.0)
        except Exception as e:
            logger.warning("Failed to get Windows master volume: %s", e)
            return 50

    def toggle_mute(self) -> ActionResult:
        """Toggle system audio mute state."""
        endpoint = self._get_endpoint_volume()
        if endpoint is None:
            return ActionResult(
                success=False,
                message="No active audio output endpoint detected.",
                error="Audio device unavailable",
            )

        try:
            current_mute = bool(endpoint.GetMute())
            new_mute = not current_mute
            endpoint.SetMute(1 if new_mute else 0, None)
            state_str = "muted" if new_mute else "unmuted"
            return ActionResult(
                success=True,
                message=f"Audio {state_str}.",
                data={"is_muted": new_mute},
            )
        except Exception as e:
            logger.exception("Error toggling Windows mute state")
            return ActionResult(
                success=False,
                message="Failed to toggle audio mute.",
                error=str(e),
            )

    def set_app_volume(self, app_name: str, percent: int) -> ActionResult:
        """Set volume percentage for a specific running application session."""
        clamped = self._clamp_volume(percent)
        if AudioUtilities is None:
            return ActionResult(
                success=False,
                message="Audio session manager is not available.",
                error="pycaw unavailable",
            )

        try:
            sessions = AudioUtilities.GetAllSessions()
            target_lower = app_name.lower().strip()
            target_stem, _ = os.path.splitext(target_lower)
            scalar = clamped / 100.0
            matched_any = False

            for session in sessions:
                proc = session.Process
                if proc is not None:
                    proc_name = proc.name().lower()
                    proc_stem, _ = os.path.splitext(proc_name)
                    if (
                        (target_lower in proc_name or target_stem == proc_stem)
                        and hasattr(session, "SimpleAudioVolume")
                        and session.SimpleAudioVolume
                    ):
                        session.SimpleAudioVolume.SetMasterVolume(scalar, None)
                        matched_any = True

            if matched_any:
                return ActionResult(
                    success=True,
                    message=f"Set {app_name} volume to {clamped}%.",
                    data={"app_name": app_name, "volume": clamped},
                )
            return ActionResult(
                success=False,
                message=f"No active audio stream found for '{app_name}'.",
                error="Session not found",
            )
        except Exception as e:
            logger.exception("Error setting per-app volume for '%s'", app_name)
            return ActionResult(
                success=False,
                message=f"Failed to adjust volume for '{app_name}'.",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Media Control (SendInput)
    # -------------------------------------------------------------------------

    def _send_media_key(self, vk_code: int) -> ActionResult:
        """Dispatch a virtual media key event via SendInput."""
        if not self._windll or not hasattr(self._windll, "user32"):
            return ActionResult(
                success=False,
                message="SendInput is not supported on this environment.",
                error="Win32 user32 unavailable",
            )

        try:
            extra = ctypes.c_ulong(0)
            p_extra = ctypes.pointer(extra)

            # Key Down
            ki_down = KeyBdInput(
                wVk=vk_code,
                wScan=0,
                dwFlags=KEYEVENTF_EXTENDEDKEY,
                time=0,
                dwExtraInfo=p_extra,
            )
            inp_down = Input(type=INPUT_KEYBOARD, ii=Input_I(ki=ki_down))

            # Key Up
            ki_up = KeyBdInput(
                wVk=vk_code,
                wScan=0,
                dwFlags=KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP,
                time=0,
                dwExtraInfo=p_extra,
            )
            inp_up = Input(type=INPUT_KEYBOARD, ii=Input_I(ki=ki_up))

            events = (Input * 2)(inp_down, inp_up)
            sent = self._windll.user32.SendInput(2, events, ctypes.sizeof(Input))
            if sent == 2:
                return ActionResult(success=True, message="Media command executed.")

            # Fallback for background / headless / non-interactive sessions: WM_APPCOMMAND
            app_cmd_map = {
                VK_MEDIA_PLAY_PAUSE: APPCOMMAND_MEDIA_PLAY_PAUSE,
                VK_MEDIA_NEXT_TRACK: APPCOMMAND_MEDIA_NEXTTRACK,
                VK_MEDIA_PREV_TRACK: APPCOMMAND_MEDIA_PREVIOUSTRACK,
                VK_MEDIA_STOP: APPCOMMAND_MEDIA_STOP,
            }
            app_cmd = app_cmd_map.get(vk_code)
            if app_cmd is not None:
                lParam = app_cmd << 16
                res = wintypes.DWORD()
                ret = self._windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_APPCOMMAND,
                    0,
                    lParam,
                    SMTO_ABORTIFHUNG,
                    500,
                    ctypes.byref(res),
                )
                if ret != 0:
                    return ActionResult(
                        success=True, message="Media command executed via system broadcast."
                    )

            return ActionResult(
                success=False,
                message="Failed to dispatch media key event.",
                error=f"SendInput returned {sent}",
            )
        except Exception as e:
            logger.exception("Failed to dispatch media key %s via SendInput", hex(vk_code))
            return ActionResult(
                success=False,
                message="Failed to send media command.",
                error=str(e),
            )

    def media_play_pause(self) -> ActionResult:
        """Toggle media playback (play/pause)."""
        return self._send_media_key(VK_MEDIA_PLAY_PAUSE)

    def media_next(self) -> ActionResult:
        """Skip to next media track."""
        return self._send_media_key(VK_MEDIA_NEXT_TRACK)

    def media_previous(self) -> ActionResult:
        """Return to previous media track."""
        return self._send_media_key(VK_MEDIA_PREV_TRACK)

    def media_stop(self) -> ActionResult:
        """Stop active media playback."""
        return self._send_media_key(VK_MEDIA_STOP)

    # -------------------------------------------------------------------------
    # Theme Switching & Desktop Broadcast
    # -------------------------------------------------------------------------

    def toggle_dark_mode(self) -> ActionResult:
        """Toggle between Windows dark and light themes and broadcast the change."""
        if winreg is None:
            return ActionResult(
                success=False,
                message="Registry access is not available on this platform.",
                error="winreg unavailable",
            )

        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        try:
            # 1. Read current value
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ) as key:
                current_apps_theme, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")

            # 2. Invert theme (0 = Dark, 1 = Light)
            new_theme = 0 if current_apps_theme == 1 else 1

            # 3. Write inverted theme
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_theme)
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_theme)

            # 4. Broadcast WM_SETTINGCHANGE via SendMessageTimeoutW
            if self._windll and hasattr(self._windll, "user32"):
                result = wintypes.DWORD()
                self._windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    "ImmersiveColorSet",
                    SMTO_ABORTIFHUNG,
                    1000,
                    ctypes.byref(result),
                )

            theme_name = "light" if new_theme == 1 else "dark"
            return ActionResult(
                success=True,
                message=f"Switched to {theme_name} theme.",
                data={"theme": theme_name},
            )

        except Exception as e:
            logger.exception("Failed to toggle Windows theme in registry")
            return ActionResult(
                success=False,
                message="Failed to toggle desktop theme.",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Application Discovery & Launching
    # -------------------------------------------------------------------------

    def _find_app_target(self, app_name: str) -> str | None:
        """Discover the executable or shortcut path for a requested application."""
        clean_name = app_name.strip()
        name_lower = clean_name.lower()

        # 1. Check if direct valid file path
        if os.path.exists(clean_name):
            return clean_name

        # 2. Check built-in standard Windows applications
        standard_apps: dict[str, str] = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "paint": "mspaint.exe",
            "mspaint": "mspaint.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "taskmgr": "taskmgr.exe",
        }
        if name_lower in standard_apps:
            return standard_apps[name_lower]

        # 3. Check Windows Start Menu shortcuts (.lnk files)
        app_data = os.environ.get("APPDATA", "")
        all_users = os.environ.get("ALLUSERSPROFILE", "")
        shortcut_dirs = []
        if app_data:
            shortcut_dirs.append(
                os.path.join(app_data, "Microsoft", "Windows", "Start Menu", "Programs")
            )
        if all_users:
            shortcut_dirs.append(
                os.path.join(all_users, "Microsoft", "Windows", "Start Menu", "Programs")
            )

        stem_lower, _ = os.path.splitext(name_lower)
        for directory in shortcut_dirs:
            if not os.path.isdir(directory):
                continue
            for lnk_path in glob.glob(os.path.join(directory, "**", "*.lnk"), recursive=True):
                lnk_stem = os.path.splitext(os.path.basename(lnk_path))[0].lower()
                if lnk_stem == stem_lower or name_lower in lnk_stem:
                    return lnk_path

        # 4. Check Registry App Paths
        if winreg is not None:
            reg_roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
            exe_cand = f"{stem_lower}.exe"
            for root in reg_roots:
                app_path_key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_cand}"
                try:
                    with winreg.OpenKey(root, app_path_key, 0, winreg.KEY_READ) as k:
                        val, _ = winreg.QueryValueEx(k, "")
                        if val and os.path.exists(val):
                            return str(val)
                except OSError:
                    continue

        return None

    def launch_app(self, app_name_or_target: str) -> ActionResult:
        """Launch an application using os.startfile (safe non-shell execution)."""
        target = self._find_app_target(app_name_or_target)
        if not target:
            return ActionResult(
                success=False,
                message=f"Could not find application '{app_name_or_target}'.",
                error="Application target not found",
            )

        try:
            # os.startfile opens applications via Windows Shell without invoking cmd or powershell
            startfile = getattr(os, "startfile", None)
            if startfile is not None:
                startfile(target)
            else:
                return ActionResult(
                    success=False,
                    message="os.startfile is only available on Windows.",
                    error="Not supported on non-Windows platforms",
                )
            return ActionResult(
                success=True,
                message=f"Launched {app_name_or_target}.",
                data={"target": target},
            )
        except Exception as e:
            logger.exception("Failed to launch application target: %s", target)
            return ActionResult(
                success=False,
                message=f"Failed to launch '{app_name_or_target}'.",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Application Closing & Process Deny-List
    # -------------------------------------------------------------------------

    def _send_wm_close(self, pid: int) -> bool:
        """Send WM_CLOSE to all top-level windows of a given PID."""
        if not self._windll or not hasattr(self._windll, "user32"):
            return False

        found_windows: list[int] = []

        def enum_windows_callback(hwnd: int, lparam: int) -> bool:
            win_pid = wintypes.DWORD()
            self._windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
            if win_pid.value == pid:
                self._windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                found_windows.append(hwnd)
            return True

        try:
            winfunctype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
            WNDENUMPROC = winfunctype(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            cb = WNDENUMPROC(enum_windows_callback)
            self._windll.user32.EnumWindows(cb, 0)
            return len(found_windows) > 0
        except Exception as e:
            logger.debug("EnumWindows WM_CLOSE failed for PID %d: %s", pid, e)
            return False

    def close_app(self, app_name_or_target: str) -> ActionResult:
        """Gracefully close a running process by sending WM_CLOSE with terminate fallback."""
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
                # Step 1: Send graceful WM_CLOSE
                self._send_wm_close(proc.pid)
                # Wait up to 1.5 seconds for graceful exit
                try:
                    proc.wait(timeout=1.5)
                    closed_count += 1
                    continue
                except psutil.TimeoutExpired:
                    pass

                # Step 2: Graceful terminate
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                    closed_count += 1
                    continue
                except psutil.TimeoutExpired:
                    pass

                # Step 3: Force kill fallback
                proc.kill()
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
        """Lock the Windows user session."""
        if not self._windll or not hasattr(self._windll, "user32"):
            return ActionResult(
                success=False,
                message="LockWorkStation is not available on this platform.",
                error="Win32 user32 unavailable",
            )

        try:
            res = self._windll.user32.LockWorkStation()
            if res:
                return ActionResult(success=True, message="Workstation locked.")
            return ActionResult(
                success=False,
                message="Failed to lock workstation.",
                error=f"LockWorkStation returned {res}",
            )
        except Exception as e:
            logger.exception("Error calling LockWorkStation")
            return ActionResult(
                success=False,
                message="Failed to lock workstation.",
                error=str(e),
            )

    def suspend_system(self) -> ActionResult:
        """Put computer into suspend / sleep mode via SetSuspendState."""
        if not self._windll or not hasattr(self._windll, "powrprof"):
            return ActionResult(
                success=False,
                message="SetSuspendState is not available on this platform.",
                error="Win32 powrprof unavailable",
            )

        try:
            # SetSuspendState(bHibernate=0, bForce=0, bWakeupEventsDisabled=0)
            res = self._windll.powrprof.SetSuspendState(0, 0, 0)
            if res:
                return ActionResult(success=True, message="System entering sleep mode.")
            return ActionResult(
                success=False,
                message="Failed to put system to sleep.",
                error=f"SetSuspendState returned {res}",
            )
        except Exception as e:
            logger.exception("Error calling SetSuspendState")
            return ActionResult(
                success=False,
                message="Failed to put system to sleep.",
                error=str(e),
            )

    # -------------------------------------------------------------------------
    # Virtual Keyboard Input Control
    # -------------------------------------------------------------------------

    def type_text(self, text: str) -> ActionResult:
        """Type text into currently focused window using Win32 SendInput Unicode events."""
        if not self._windll or not hasattr(self._windll, "user32"):
            return ActionResult(
                success=False,
                message="SendInput is not available on this platform.",
                error="Win32 user32 unavailable",
            )

        try:
            extra = ctypes.c_ulong(0)
            p_extra = ctypes.pointer(extra)
            # Send character by character using KEYEVENTF_UNICODE
            for ch in text:
                code = ord(ch)
                down = Input(
                    type=INPUT_KEYBOARD,
                    ii=Input_I(
                        ki=KeyBdInput(
                            wVk=0,
                            wScan=code,
                            dwFlags=KEYEVENTF_UNICODE,
                            time=0,
                            dwExtraInfo=p_extra,
                        )
                    ),
                )
                up = Input(
                    type=INPUT_KEYBOARD,
                    ii=Input_I(
                        ki=KeyBdInput(
                            wVk=0,
                            wScan=code,
                            dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                            time=0,
                            dwExtraInfo=p_extra,
                        )
                    ),
                )
                inputs = (Input * 2)(down, up)
                sent = self._windll.user32.SendInput(2, inputs, ctypes.sizeof(Input))
                if sent != 2 and hasattr(self._windll.user32, "keybd_event"):
                    self._windll.user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
                    self._windll.user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)

            return ActionResult(
                success=True,
                message="Typed text into active window.",
                data={"length": len(text)},
            )
        except Exception as e:
            logger.exception("Failed to type text via SendInput")
            return ActionResult(
                success=False,
                message="Failed to type text.",
                error=str(e),
            )

    def press_key(self, key: str) -> ActionResult:
        """Simulate a single virtual key press in the active window."""
        clean_key = key.strip().lower()
        vk = WIN_KEY_MAP.get(clean_key)
        if vk is None:
            return ActionResult(
                success=False,
                message=f"Unsupported key: '{clean_key}'.",
                error=f"Unsupported virtual key: {clean_key}",
            )

        if not self._windll or not hasattr(self._windll, "user32"):
            return ActionResult(
                success=False,
                message="SendInput is not available on this platform.",
                error="Win32 user32 unavailable",
            )

        try:
            extra = ctypes.c_ulong(0)
            p_extra = ctypes.pointer(extra)
            down = Input(
                type=INPUT_KEYBOARD,
                ii=Input_I(
                    ki=KeyBdInput(
                        wVk=vk,
                        wScan=0,
                        dwFlags=0,
                        time=0,
                        dwExtraInfo=p_extra,
                    )
                ),
            )
            up = Input(
                type=INPUT_KEYBOARD,
                ii=Input_I(
                    ki=KeyBdInput(
                        wVk=vk,
                        wScan=0,
                        dwFlags=KEYEVENTF_KEYUP,
                        time=0,
                        dwExtraInfo=p_extra,
                    )
                ),
            )
            inputs = (Input * 2)(down, up)
            sent = self._windll.user32.SendInput(2, inputs, ctypes.sizeof(Input))
            if sent == 2:
                return ActionResult(
                    success=True,
                    message=f"Pressed {clean_key} key.",
                    data={"key": clean_key, "vk": vk},
                )

            # Fallback to keybd_event if SendInput did not inject both events (e.g. background sessions)
            if hasattr(self._windll.user32, "keybd_event"):
                self._windll.user32.keybd_event(vk, 0, 0, 0)
                self._windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                return ActionResult(
                    success=True,
                    message=f"Pressed {clean_key} key.",
                    data={"key": clean_key, "vk": vk},
                )

            return ActionResult(
                success=False,
                message=f"Failed to press key {clean_key}.",
                error="SendInput returned 0",
            )
        except Exception as e:
            logger.exception("Failed to send key press: %s", clean_key)
            return ActionResult(
                success=False,
                message=f"Failed to press key {clean_key}.",
                error=str(e),
            )

    def unmute_current_process(self) -> None:
        """Ensure current process audio session in Windows Core Audio is not muted or attenuated."""
        if AudioUtilities is None:
            return
        try:
            pid = os.getpid()
            for session in AudioUtilities.GetAllSessions():
                if session.Process and session.ProcessId == pid:
                    vol = getattr(session, "SimpleAudioVolume", None)
                    if vol is not None:
                        if vol.GetMute():
                            vol.SetMute(0, None)
                        if vol.GetMasterVolume() < 0.5:
                            vol.SetMasterVolume(1.0, None)
        except Exception:
            logger.debug("Failed to check or unmute current process volume", exc_info=True)
