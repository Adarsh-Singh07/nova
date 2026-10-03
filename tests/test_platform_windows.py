"""Unit tests for WindowsPlatformAdapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from nova.platform.windows import WindowsPlatformAdapter


@pytest.fixture
def win_adapter() -> WindowsPlatformAdapter:
    return WindowsPlatformAdapter()


def test_windows_volume_operations(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_endpoint = MagicMock()
    mock_endpoint.GetMasterVolumeLevelScalar.return_value = 0.65
    mock_endpoint.GetMute.return_value = 0

    mock_speakers = MagicMock()
    mock_speakers.EndpointVolume = mock_endpoint

    mock_audio_utils = MagicMock()
    mock_audio_utils.GetSpeakers.return_value = mock_speakers
    monkeypatch.setattr("nova.platform.windows.AudioUtilities", mock_audio_utils)

    # 1. Get Volume
    vol = win_adapter.get_volume()
    assert vol == 65

    # 2. Set Volume
    res = win_adapter.set_volume(80)
    assert res.success is True
    assert "80%" in res.message
    mock_endpoint.SetMasterVolumeLevelScalar.assert_called_with(0.8, None)

    # 3. Toggle Mute
    res_mute = win_adapter.toggle_mute()
    assert res_mute.success is True
    assert "muted" in res_mute.message
    mock_endpoint.SetMute.assert_called_with(1, None)


def test_windows_volume_endpoint_unavailable(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate missing sound card or headless environment
    mock_audio_utils = MagicMock()
    mock_audio_utils.GetSpeakers.return_value = None
    monkeypatch.setattr("nova.platform.windows.AudioUtilities", mock_audio_utils)

    # Get volume safe fallback
    assert win_adapter.get_volume() == 50

    # Set volume graceful error
    res_set = win_adapter.set_volume(70)
    assert res_set.success is False
    assert "No active audio output endpoint" in res_set.message

    # Toggle mute graceful error
    res_mute = win_adapter.toggle_mute()
    assert res_mute.success is False
    assert "No active audio output endpoint" in res_mute.message


def test_windows_per_app_volume(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_sav = MagicMock()
    mock_proc = MagicMock()
    mock_proc.name.return_value = "spotify.exe"

    mock_session = MagicMock()
    mock_session.Process = mock_proc
    mock_session.SimpleAudioVolume = mock_sav

    mock_audio_utils = MagicMock()
    mock_audio_utils.GetAllSessions.return_value = [mock_session]
    monkeypatch.setattr("nova.platform.windows.AudioUtilities", mock_audio_utils)

    # Match existing process
    res = win_adapter.set_app_volume("spotify", 45)
    assert res.success is True
    assert "45%" in res.message
    mock_sav.SetMasterVolume.assert_called_with(0.45, None)

    # Missing process
    res_missing = win_adapter.set_app_volume("discord", 50)
    assert res_missing.success is False
    assert "No active audio stream found" in res_missing.message


def test_windows_media_keys(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_user32 = MagicMock()
    mock_user32.SendInput.return_value = 2
    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    monkeypatch.setattr(win_adapter, "_windll", mock_windll)

    res1 = win_adapter.media_play_pause()
    assert res1.success is True
    assert mock_user32.SendInput.call_count == 1

    res2 = win_adapter.media_next()
    assert res2.success is True

    res3 = win_adapter.media_previous()
    assert res3.success is True

    res4 = win_adapter.media_stop()
    assert res4.success is True


def test_windows_theme_toggle(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_winreg = MagicMock()
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (1, 1)  # Currently light theme

    monkeypatch.setattr("nova.platform.windows.winreg", mock_winreg)

    mock_user32 = MagicMock()
    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    monkeypatch.setattr(win_adapter, "_windll", mock_windll)

    res = win_adapter.toggle_dark_mode()
    assert res.success is True
    assert res.data["theme"] == "dark"
    assert "dark" in res.message


def test_windows_app_discovery_and_launch(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Built-in standard app lookup
    assert win_adapter._find_app_target("notepad") == "notepad.exe"
    assert win_adapter._find_app_target("calc") == "calc.exe"

    # Nonexistent app lookup
    assert win_adapter._find_app_target("definitely_fake_app_12345") is None

    # Failed launch
    res_fail = win_adapter.launch_app("definitely_fake_app_12345")
    assert res_fail.success is False

    # Successful launch mock
    mock_startfile = MagicMock()
    monkeypatch.setattr("os.startfile", mock_startfile, raising=False)

    res_ok = win_adapter.launch_app("notepad")
    assert res_ok.success is True
    mock_startfile.assert_called_with("notepad.exe")


def test_windows_app_close(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. Reject critical process
    res_crit = win_adapter.close_app("explorer.exe")
    assert res_crit.success is False

    # 2. Process not found
    monkeypatch.setattr("psutil.process_iter", lambda *args, **kwargs: [])
    res_none = win_adapter.close_app("notepad")
    assert res_none.success is False
    assert "No running process found" in res_none.message

    # 3. Graceful close process
    mock_proc = MagicMock()
    mock_proc.info = {"name": "notepad.exe"}
    mock_proc.pid = 9999
    mock_proc.wait.return_value = True

    monkeypatch.setattr("psutil.process_iter", lambda *args, **kwargs: [mock_proc])
    monkeypatch.setattr(win_adapter, "_send_wm_close", lambda pid: True)

    res_close = win_adapter.close_app("notepad")
    assert res_close.success is True
    assert "Closed notepad" in res_close.message


def test_windows_system_lock_and_suspend(
    win_adapter: WindowsPlatformAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_user32 = MagicMock()
    mock_user32.LockWorkStation.return_value = 1

    mock_powrprof = MagicMock()
    mock_powrprof.SetSuspendState.return_value = 1

    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    mock_windll.powrprof = mock_powrprof
    monkeypatch.setattr(win_adapter, "_windll", mock_windll)

    res_lock = win_adapter.lock_workstation()
    assert res_lock.success is True
    assert "Workstation locked" in res_lock.message

    res_sleep = win_adapter.suspend_system()
    assert res_sleep.success is True
    assert "sleep" in res_sleep.message
