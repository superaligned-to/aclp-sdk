import asyncio
import json
import socket
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypeVar, cast

import pytest
import uvicorn

import aclp
from aclp.events import EventMethod

T = TypeVar("T")

Flavor: TypeAlias = Literal["sync", "async"]

EXAMPLES: list[tuple[str, dict[str, object]]] = [
    (m, p) for m, p in json.loads((Path(__file__).parent / "event-examples.json").read_text())
]

CONTEXT = aclp.ResultSchema[dict[str, list[str]]](
    {
        "type": "object",
        "properties": {"context": {"type": "array", "items": {"type": "string"}}},
        "required": ["context"],
        "additionalProperties": False,
    }
)

INPUT: dict[str, object] = {
    "sessionId": "session-1",
    "content": [{"type": "text", "text": "Create a class."}],
}


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def params(method: str) -> dict[str, object]:
    return next(p for m, p in EXAMPLES if m == method)


class SyncShim:
    """The sync client behind the async client's method shapes, so one suite covers both."""

    def __init__(self, client: aclp.Client) -> None:
        self.client = client

    async def request(
        self, method: EventMethod, params: Mapping[str, object], result: aclp.ResultSchema[T]
    ) -> T:
        return self.client.request(method, params, result)

    def notify(self, method: EventMethod, params: Mapping[str, object]) -> None:
        self.client.notify(method, params)

    async def flush(self) -> None:
        self.client.flush()

    def failure_policy(self, method: str) -> aclp.OnError:
        return self.client.failure_policy(method)


AnyClient: TypeAlias = aclp.AsyncClient | SyncShim


@asynccontextmanager
async def open_client(flavor: Flavor, url: str, **opts: Any) -> AsyncIterator[AnyClient]:
    if flavor == "async":
        provider = opts.get("authorization")

        if callable(provider):

            async def authorize() -> str:
                return cast("str", provider())

            opts["authorization"] = authorize

        async with aclp.AsyncClient(url, **opts) as client:
            yield client
    else:
        with aclp.Client(url, **opts) as sync:
            yield SyncShim(sync)


async def discover(flavor: Flavor, url: str, **opts: Any) -> aclp.events.DiscoveryDocument:
    if flavor == "async":
        return await aclp.discover_async(url, **opts)

    return aclp.discover(url, **opts)


@pytest.fixture(params=["sync", "async"])
def flavor(request: pytest.FixtureRequest) -> Flavor:
    return cast("Flavor", request.param)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def serve(app: aclp.ASGIApp, **opts: Any) -> Iterator[int]:
    port = free_port()
    cfg = uvicorn.Config(cast("Any", app), host="127.0.0.1", port=port, log_level="warning", **opts)
    server = uvicorn.Server(cfg)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.01)

    try:
        yield port
    finally:
        server.should_exit = True
        thread.join()


@contextmanager
def scripted(
    reply: bytes | Callable[[bytes], Awaitable[bytes]], *, delay: float = 0
) -> Iterator[int]:
    """A raw TCP server that answers each connection with fixed bytes or a reply built from the request."""
    port = free_port()
    ready = threading.Event()
    stop: asyncio.Event | None = None
    loop: asyncio.AbstractEventLoop | None = None

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = await reader.readuntil(b"\r\n\r\n")
        length = next(
            (
                int(x.split(b":")[1])
                for x in head.split(b"\r\n")
                if x.lower().startswith(b"content-length:")
            ),
            0,
        )
        req = head + await reader.readexactly(length)
        await asyncio.sleep(delay)
        writer.write(reply if isinstance(reply, bytes) else await reply(req))
        await writer.drain()
        writer.close()

    async def main() -> None:
        nonlocal stop, loop
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        server = await asyncio.start_server(handle, "127.0.0.1", port)

        async with server:
            ready.set()
            await stop.wait()

    thread = threading.Thread(target=asyncio.run, args=(main(),), daemon=True)
    thread.start()
    ready.wait()

    try:
        yield port
    finally:
        assert loop is not None
        assert stop is not None
        loop.call_soon_threadsafe(stop.set)
        thread.join()


def http_reply(status: int, body: bytes, *headers: str) -> bytes:
    head = [f"HTTP/1.1 {status} X", f"Content-Length: {len(body)}", *headers]
    return ("\r\n".join(head) + "\r\n\r\n").encode() + body


@pytest.fixture(scope="session")
def tls(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str, str]:
    import trustme

    ca = trustme.CA()
    cert = ca.issue_cert("localhost", "127.0.0.1")
    tmp = tmp_path_factory.mktemp("tls")
    certfile = tmp / "cert.pem"
    keyfile = tmp / "key.pem"
    cert.private_key_pem.write_to_path(str(keyfile))
    cert.cert_chain_pems[0].write_to_path(str(certfile))
    return ca.cert_pem.bytes().decode(), str(certfile), str(keyfile)
