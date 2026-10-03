"""Universal contract tests ensuring all platform adapters adhere to PlatformAdapterProtocol."""

from __future__ import annotations

import pytest

from nova.core.fakes import FakePlatformAdapter
from nova.core.interfaces import ActionResult, PlatformAdapterProtocol
from nova.platform.base import BasePlatformAdapter
from nova.platform.linux import LinuxPlatformAdapter
from nova.platform.windows import WindowsPlatformAdapter


@pytest.fixture(params=[FakePlatformAdapter, WindowsPlatformAdapter, LinuxPlatformAdapter])
def adapter(request: pytest.FixtureRequest) -> BasePlatformAdapter | FakePlatformAdapter:
    return request.param()  # type: ignore[no-any-return]


def test_platform_adapter_protocol_compliance(
    adapter: BasePlatformAdapter | FakePlatformAdapter,
) -> None:
    """Verify adapter satisfies PlatformAdapterProtocol runtime check."""
    assert isinstance(adapter, PlatformAdapterProtocol)


def test_critical_process_deny_list(
    adapter: BasePlatformAdapter | FakePlatformAdapter,
) -> None:
    """Verify protected system processes cannot be closed."""
    critical_names = [
        "explorer.exe",
        "explorer",
        "system",
        "csrss.exe",
        "systemd",
        "kwin",
        "nova",
        "nova.exe",
    ]

    for name in critical_names:
        res = adapter.close_app(name)
        assert isinstance(res, ActionResult)
        assert res.success is False
        assert "Refused to terminate" in res.message or "protected" in res.message.lower()


def test_invalid_url_protocol_refusal(
    adapter: BasePlatformAdapter | FakePlatformAdapter,
) -> None:
    """Verify non-HTTP(S) URLs are strictly rejected."""
    bad_urls = [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,<h1>bad</h1>",
        "cmd.exe /c calc",
    ]

    for url in bad_urls:
        res = adapter.open_url(url)
        assert isinstance(res, ActionResult)
        assert res.success is False
