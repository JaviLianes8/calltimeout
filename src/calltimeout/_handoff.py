"""Pickle what a starting child receives so each handle in it is that child's alone."""

from __future__ import annotations

import io
import sys
from multiprocessing.context import get_spawning_popen
from multiprocessing.reduction import ForkingPickler
from typing import Any

if sys.platform == "win32":
    import socket
    from multiprocessing import connection

    def _pipe_end(handle: int, readable: bool, writable: bool) -> connection.PipeConnection:
        return connection.PipeConnection(handle, readable, writable)

    def _shared_socket(shared: bytes) -> socket.socket:
        return socket.fromshare(shared)

    def _socket_connection(shared: bytes, readable: bool, writable: bool) -> object:
        return connection.Connection(socket.fromshare(shared).detach(), readable, writable)

    class _ToChild(ForkingPickler):
        """Puts each pipe end and socket straight into the child being started.

        multiprocessing duplicates them into this process for the child to take, and a
        child stopped before it takes one leaves that duplicate open here for good.
        """

        def __init__(self, file: io.BytesIO, popen: Any) -> None:
            super().__init__(file)
            self.popen = popen

        def reducer_override(self, obj: Any) -> Any:
            kind = type(obj)
            if kind is connection.PipeConnection:
                handle = self.popen.duplicate_for_child(obj.fileno())
                return (_pipe_end, (handle, obj.readable, obj.writable))
            if kind is socket.socket:
                return (_shared_socket, (obj.share(self.popen.pid),))
            if kind is connection.Connection:  # a socket on Windows
                with socket.fromfd(obj.fileno(), socket.AF_INET, socket.SOCK_STREAM) as copy:
                    shared = copy.share(self.popen.pid)
                return (_socket_connection, (shared, obj.readable, obj.writable))
            return NotImplemented

else:

    class _ToChild(ForkingPickler):
        """A POSIX start passes descriptors to the child itself (pass_fds, forkserver)."""

        def __init__(self, file: io.BytesIO, popen: Any) -> None:
            super().__init__(file)


def dumps_for_child(obj: object) -> bytes:
    """Pickle obj for the child of the Process.start() now running."""
    popen = get_spawning_popen()
    if popen is None:
        raise RuntimeError("only Process.start() sends this to a child")
    buffer = io.BytesIO()
    _ToChild(buffer, popen).dump(obj)
    return buffer.getvalue()
