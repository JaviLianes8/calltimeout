"""Run a command and then end every process it left behind, also orphans.

A mutant can make a decorated function start a child that starts another, without end:
the processes outlive the suite that started them. On POSIX the command gets its own
session and the whole group is killed afterwards; on Windows it runs inside a job object
that kills every process in it when closed.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
from pathlib import Path


def run_tree(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    """Like subprocess.run with captured text output, then kill whatever is still running."""
    if sys.platform == "win32":
        return _run_in_job(command, cwd, timeout)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        out, _ = process.communicate(timeout=timeout)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    return subprocess.CompletedProcess(command, process.returncode, out, "")


def _run_in_job(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle_t, dword = wintypes.HANDLE, wintypes.DWORD
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = handle_t
    kernel32.SetInformationJobObject.argtypes = [handle_t, ctypes.c_int, ctypes.c_void_p, dword]
    kernel32.OpenProcess.argtypes = [dword, wintypes.BOOL, dword]
    kernel32.OpenProcess.restype = handle_t
    kernel32.AssignProcessToJobObject.argtypes = [handle_t, handle_t]
    kernel32.CloseHandle.argtypes = [handle_t]

    class _Limits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _Extended(ctypes.Structure):
        _fields_ = [
            ("Basic", _Limits),
            ("IoInfo", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job = kernel32.CreateJobObjectW(None, None)
    info = _Extended()
    info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=0x4,  # CREATE_SUSPENDED: in the job before it can start anything
    )
    handle = kernel32.OpenProcess(0x1F0FFF, False, process.pid)
    kernel32.AssignProcessToJobObject(job, handle)
    _resume(kernel32, process.pid)
    try:
        out, _ = process.communicate(timeout=timeout)
    finally:
        kernel32.CloseHandle(job)  # kills every process still in the job
        kernel32.CloseHandle(handle)
        process.wait()
    return subprocess.CompletedProcess(command, process.returncode, out, "")


def _resume(kernel32: object, pid: int) -> None:
    import ctypes

    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
    handle = kernel32.OpenProcess(0x0800, False, pid)  # type: ignore[attr-defined]
    ntdll.NtResumeProcess(handle)
    kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
