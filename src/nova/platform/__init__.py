"""Platform adapter factory and concrete platform implementations."""

from __future__ import annotations

import sys

from nova.core.fakes import FakePlatformAdapter
from nova.core.interfaces import PlatformAdapterProtocol
from nova.platform.base import BasePlatformAdapter
from nova.platform.linux import LinuxPlatformAdapter
from nova.platform.windows import WindowsPlatformAdapter

__all__ = [
    "BasePlatformAdapter",
    "LinuxPlatformAdapter",
    "WindowsPlatformAdapter",
    "get_platform_adapter",
]


def get_platform_adapter() -> PlatformAdapterProtocol:
    """Return the active operating system platform adapter."""
    if sys.platform == "win32":
        return WindowsPlatformAdapter()
    if sys.platform.startswith("linux"):
        return LinuxPlatformAdapter()
    return FakePlatformAdapter()
