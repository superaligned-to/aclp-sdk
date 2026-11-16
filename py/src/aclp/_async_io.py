import asyncio
import contextlib
import ssl
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, ParamSpec, TypeAlias, TypeVar

from aclp._endpoint import Endpoint
from aclp._errors import AuthorizationError, DeadlineError, TransportError
from aclp._http import MAX_LINE_BYTES

T = TypeVar("T")

P = ParamSpec("P")

Authorization: TypeAlias = str | Callable[[], Awaitable[str]]


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()

    if left <= 0:
        raise DeadlineError("ACLP request deadline exceeded")

    return left


async def authorize(auth: Authorization, deadline: float) -> str:
    if isinstance(auth, str):
        return auth

    try:
        async with asyncio.timeout(_remaining(deadline)):
            val = await auth()
    except TimeoutError as err:
        raise DeadlineError("ACLP request deadline exceeded") from err
    except Exception as err:  # the provider is caller code with no declared errors
        raise AuthorizationError("ACLP authorization provider failed") from err

    if not isinstance(val, str):
        raise AuthorizationError("ACLP authorization provider returned a non-string value")

    return val


class Stream:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, deadline: float
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._deadline = deadline

    async def _timed(self, aw: Awaitable[T]) -> T:
        try:
            async with asyncio.timeout(_remaining(self._deadline)):
                return await aw
        except TimeoutError as err:
            raise DeadlineError("ACLP request deadline exceeded") from err
        except asyncio.IncompleteReadError as err:
            raise TransportError("ACLP connection closed before a complete response") from err
        except (OSError, ValueError) as err:
            raise TransportError("ACLP transport failed") from err

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._timed(self._writer.drain())

    async def readline(self) -> bytes:
        line = await self._timed(self._reader.readline())

        if not line.endswith(b"\n"):
            raise TransportError("ACLP connection closed before a complete response")

        return line

    async def readexactly(self, n: int) -> bytes:
        return await self._timed(self._reader.readexactly(n))

    async def read(self, n: int) -> bytes:
        return await self._timed(self._reader.read(n))

    async def close(self) -> None:
        self._writer.close()

        with contextlib.suppress(OSError):
            await self._writer.wait_closed()


async def connect(ep: Endpoint, ctx: ssl.SSLContext | None, deadline: float) -> Stream:
    try:
        async with asyncio.timeout(_remaining(deadline)):
            reader, writer = await asyncio.open_connection(
                ep.host,
                ep.port,
                ssl=ctx,
                server_hostname=ep.name if ctx is not None else None,
                limit=MAX_LINE_BYTES,
            )
    except TimeoutError as err:
        raise DeadlineError("ACLP request deadline exceeded") from err
    except OSError as err:
        raise TransportError("ACLP connection failed") from err

    return Stream(reader, writer, deadline)


class Pending:
    """Notification deliveries owned by one task group, open only inside `async with`."""

    def __init__(self) -> None:
        self._group: asyncio.TaskGroup | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def open(self) -> None:
        group = asyncio.TaskGroup()
        await group.__aenter__()
        self._group = group

    def ready(self) -> bool:
        return self._group is not None

    def start(
        self, fn: Callable[P, Coroutine[Any, Any, None]], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        if self._group is None:
            return

        task = self._group.create_task(fn(*args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait(self) -> None:
        while self._tasks:
            await asyncio.wait(set(self._tasks))

    async def close(self) -> None:
        group, self._group = self._group, None

        if group is not None:
            await group.__aexit__(None, None, None)
