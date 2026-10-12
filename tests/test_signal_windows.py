"""Signal mode on Windows: refused with a clear error before anything starts."""

from __future__ import annotations

import sys

import _targets
import pytest

from calltimeout import run, with_timeout

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_windows_says_signal_mode_is_unavailable() -> None:
    with pytest.raises(NotImplementedError, match="SIGALRM"):
        run(_targets.echo, 1.0, args=(1,), mode="signal")


def test_the_platform_error_comes_before_the_zero_budget_shortcut() -> None:
    with pytest.raises(NotImplementedError):
        run(_targets.echo, 0, args=(1,), mode="signal")


def test_a_signal_mode_decorator_raises_when_called() -> None:
    echo = with_timeout(1.0, mode="signal")(_targets.echo)
    with pytest.raises(NotImplementedError):
        echo(1)
