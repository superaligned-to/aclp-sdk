import socket
import ssl
import time
from collections.abc import Callable
from typing import ParamSpec, TypeAlias

from aclp._endpoint import Endpoint
from aclp._errors import AuthorizationError, DeadlineError, TransportError
from aclp._http import MAX_LINE_BYTES

P = ParamSpec("P")

Authorization: TypeAlias = str | Callable[[], str]


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()

    if left <= 0:
        raise DeadlineError("ACLP request deadline exceeded")

    return left


def authorize(auth: Authorization, deadline: float) -> str:
    if isinstance(auth, str):
        return auth

    try:
        val = auth()
    except Exception as err:  # the provider is caller code with no declared errors
        raise AuthorizationError("ACLP authorization provider failed") from err

    _remaining(deadline)

    if not isinstance(val, str):
        raise AuthorizationError("ACLP authorization provider returned a non-string value")

    return val


class Stream:
    def __init__(self, sock: socket.socket, deadline: float) -> None:
        self._sock = sock
        self._file = sock.makefile("rb")
        self._deadline = deadline

    def _arm(self) -> None:
        self._sock.settimeout(_remaining(self._deadline))

    def write(self, data: bytes) -> None:
        self._arm()

        try:
            self._sock.sendall(data)
        except TimeoutError as err:
            raise DeadlineError("ACLP request deadline exceeded") from err
        except OSError as err:
            raise TransportError("ACLP transport failed") from err

    def _read(self, fn: Callable[[], bytes]) -> bytes:
        self._arm()

        try:
            return fn()
        except TimeoutError as err:
            raise DeadlineError("ACLP request deadline exceeded") from err
        except OSError as err:
            raise TransportError("ACLP transport failed") from err

    def readline(self) -> bytes:
        line = self._read(lambda: self._file.readline(MAX_LINE_BYTES + 1))

        if len(line) > MAX_LINE_BYTES:
            raise TransportError("ACLP transport failed")

        if not line.endswith(b"\n"):
            raise TransportError("ACLP connection closed before a complete response")

        return line

    def readexactly(self, n: int) -> bytes:
        data = self._read(lambda: self._file.read(n))

        if len(data) != n:
            raise TransportError("ACLP connection closed before a complete response")

        return data

    def read(self, n: int) -> bytes:
        return self._read(lambda: self._file.read1(n))

    def close(self) -> None:
        self._file.close()
        self._sock.close()


def connect(ep: Endpoint, ctx: ssl.SSLContext | None, deadline: float) -> Stream:
    try:
        sock = socket.create_connection((ep.host, ep.port), timeout=_remaining(deadline))
    except TimeoutError as err:
        raise DeadlineError("ACLP request deadline exceeded") from err
    except OSError as err:
        raise TransportError("ACLP connection failed") from err

    if ctx is None:
        return Stream(sock, deadline)

    try:
        sock.settimeout(_remaining(deadline))
        tls = ctx.wrap_socket(sock, server_hostname=ep.name)
    except TimeoutError as err:
        sock.close()
        raise DeadlineError("ACLP request deadline exceeded") from err
    except OSError as err:
        sock.close()
        raise TransportError("ACLP connection failed") from err
    except DeadlineError:
        sock.close()
        raise

    return Stream(tls, deadline)


class Pending:
    """The sync client delivers each notification before `notify` returns."""

    def open(self) -> None:
        return None

    def ready(self) -> bool:
        return True

    def start(self, fn: Callable[P, None], *args: P.args, **kwargs: P.kwargs) -> None:
        fn(*args, **kwargs)

    def wait(self) -> None:
        return None

    def close(self) -> None:
        return None
