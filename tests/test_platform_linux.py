"""Unit tests for LinuxPlatformAdapter."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from nova.platform.linux import LinuxPlatformAdapter


@pytest.fixture
def linux_adapter() -> LinuxPlatformAdapter:
    return LinuxPlatformAdapter()


def test_linux_wpctl_volume_operations(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. Mock wpctl presence
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/wpctl" if cmd == "wpctl" else None)

    runs = []

    def mock_run(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        runs.append(cmd)
        if "get-volume" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="Volume: 0.72 [MUTED]\n")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr("subprocess.run", mock_run)

    # Get volume
    vol = linux_adapter.get_volume()
    assert vol == 72

    # Set volume
    res_set = linux_adapter.set_volume(85)
    assert res_set.success is True
    assert "85%" in res_set.message
    assert any("set-volume" in cmd and "0.85" in cmd for cmd in runs)

    # Toggle mute
    res_mute = linux_adapter.toggle_mute()
    assert res_mute.success is True
    assert any("set-mute" in cmd and "toggle" in cmd for cmd in runs)


def test_linux_pactl_fallback(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/pactl" if cmd == "pactl" else None)

    runs = []

    def mock_run(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        runs.append(cmd)
        if "get-sink-volume" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Volume: front-left: 32768 /  50% / -18.06 dB\n"
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr("subprocess.run", mock_run)

    assert linux_adapter.get_volume() == 50

    res_set = linux_adapter.set_volume(60)
    assert res_set.success is True
    assert any("set-sink-volume" in cmd and "60%" in cmd for cmd in runs)


def test_linux_no_audio_backend(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    assert linux_adapter.get_volume() == 50
    res_set = linux_adapter.set_volume(50)
    assert res_set.success is False
    assert "No supported Linux audio manager" in res_set.message

    res_mute = linux_adapter.toggle_mute()
    assert res_mute.success is False


def test_linux_media_playerctl(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/bin/playerctl" if cmd == "playerctl" else None
    )

    runs = []

    def mock_run_media(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        runs.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr("subprocess.run", mock_run_media)

    assert linux_adapter.media_play_pause().success is True
    assert any("play-pause" in cmd for cmd in runs)

    assert linux_adapter.media_next().success is True
    assert any("next" in cmd for cmd in runs)

    assert linux_adapter.media_previous().success is True
    assert any("previous" in cmd for cmd in runs)

    assert linux_adapter.media_stop().success is True
    assert any("stop" in cmd for cmd in runs)


def test_linux_theme_gnome(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/bin/gsettings" if cmd == "gsettings" else None
    )
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")

    runs = []

    def mock_run(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        runs.append(cmd)
        if "get" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="'prefer-dark'\n")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr("subprocess.run", mock_run)

    res = linux_adapter.toggle_dark_mode()
    assert res.success is True
    assert res.data["theme"] == "light"
    assert any("set" in cmd and "default" in cmd for cmd in runs)


def test_linux_app_discovery_desktop_file(
    linux_adapter: LinuxPlatformAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Create fake desktop entry
    desktop_file = tmp_path / "vlc.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\n"
        "Name=VLC media player\n"
        "Exec=/usr/bin/vlc --started-from-file %U\n"
        "Type=Application\n"
    )

    monkeypatch.setattr("glob.glob", lambda pat: [str(desktop_file)])
    monkeypatch.setattr("os.path.isdir", lambda d: True)
    monkeypatch.setattr("shutil.which", lambda cmd: cmd if "vlc" in cmd else None)

    parts = linux_adapter._find_desktop_entry("vlc")
    assert parts is not None
    assert parts[0] == "/usr/bin/vlc"
    assert "%U" not in parts


def test_linux_app_launch(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux_adapter, "_find_desktop_entry", lambda name: ["/usr/bin/gedit"])

    mock_popen = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    res = linux_adapter.launch_app("gedit")
    assert res.success is True
    mock_popen.assert_called_once()
    assert mock_popen.call_args[0][0] == ["/usr/bin/gedit"]


def test_linux_app_close(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Reject critical process
    res_crit = linux_adapter.close_app("systemd")
    assert res_crit.success is False

    # Process not running
    monkeypatch.setattr("psutil.process_iter", lambda *args, **kwargs: [])
    res_none = linux_adapter.close_app("gedit")
    assert res_none.success is False

    # Graceful close
    mock_proc = MagicMock()
    mock_proc.info = {"name": "gedit"}
    mock_proc.wait.return_value = True

    monkeypatch.setattr("psutil.process_iter", lambda *args, **kwargs: [mock_proc])

    res_ok = linux_adapter.close_app("gedit")
    assert res_ok.success is True
    mock_proc.send_signal.assert_called_with(signal.SIGTERM)


def test_linux_lock_and_suspend(
    linux_adapter: LinuxPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "shutil.which",
        lambda cmd: f"/usr/bin/{cmd}" if cmd in ("loginctl", "systemctl") else None,
    )

    runs = []

    def mock_run_lock(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        runs.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr("subprocess.run", mock_run_lock)

    res_lock = linux_adapter.lock_workstation()
    assert res_lock.success is True
    assert any("lock-session" in cmd for cmd in runs)

    res_suspend = linux_adapter.suspend_system()
    assert res_suspend.success is True
    assert any("suspend" in cmd for cmd in runs)
