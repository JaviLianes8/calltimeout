"""Count the handles (Windows) or file descriptors (POSIX) this process has open."""

from __future__ import annotations

import ctypes
import os
import sys

import pytest


def handles() -> int:
    if sys.platform == "win32":
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        count = wintypes.DWORD()
        assert kernel32.GetProcessHandleCount(kernel32.GetCurrentProcess(), ctypes.byref(count))
        return count.value
    for folder in ("/proc/self/fd", "/dev/fd"):
        if os.path.isdir(folder):
            return len(os.listdir(folder))
    pytest.skip("no way to count this process's handles here")
