import asyncio
import hashlib
import hmac
import inspect
import ipaddress
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Generic, Never, TypeAlias, TypeVar, cast

from aclp._async_client import DISCOVERY_PATH
from aclp._errors import CallbackError, ConfigError, JsonError
from aclp._json import MAX_BODY_BYTES, decode_json, encode_json
from aclp._result import ResultSchema
from aclp._validation import (
    is_discovery_document,
    is_envelope,
    is_event_method,
    is_notification,
    request_id,
    validate_params,
    warm,
)
from aclp.events import DiscoveryAuth

P = TypeVar("P", contravariant=True)

Scope: TypeAlias = Mapping[str, object]

Message: TypeAlias = Mapping[str, object]

Receive: TypeAlias = Callable[[], Awaitable[MutableMapping[str, object]]]

Send: TypeAlias = Callable[[MutableMapping[str, object]], Awaitable[None]]

ASGIApp: TypeAlias = Callable[[Scope, Receive, Send], Awaitable[None]]

MAX_ACTIVE_CALLBACKS = 32

READ_TIMEOUT = 5.0

_LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "[::1]"})

_SCHEME = re.compile(r"([!#$%&'*+.^_`|~0-9A-Za-z-]+) +[^\s][^\r\n]*")

_PUBLIC_HOST = re.compile(r"[a-z0-9.-]+")


@dataclass(frozen=True, slots=True)
class CallContext:
    """What the server knows about a call besides its parameters.

    `client` is the self-reported `ACLP-Client` header; never use it for authorization.
    """

    __module__ = "aclp"

    client: str | None = None


@dataclass(frozen=True, slots=True)
class Callback(Generic[P]):
    """A handler for one event method, and for requests the schema its result must satisfy.

    `handle(params, ctx)` may be a coroutine function, which runs on the event loop, or a plain
    function, which runs in a worker thread. A method without `result` accepts only
    notifications; requests for it answer JSON-RPC `-32601`.
    """

    __module__ = "aclp"

    handle: Callable[[P, CallContext], object]
    result: ResultSchema[object] | None = None


@dataclass(frozen=True, slots=True)
class Discovery:
    """What `GET /.well-known/aclp` publishes besides the registered methods.

    `endpoint` is the absolute URL clients post ACLP messages to. Without `auth`, the document
    lists `token` exactly when the server requires authorization.
    """

    __module__ = "aclp"

    endpoint: str
    name: str | None = None
    auth: DiscoveryAuth | None = None


class _Reject(Exception):  # noqa: N818  # control flow inside the app, never raised to callers
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


def _loopback(addr: object) -> bool:
    if not isinstance(addr, str):
        return False

    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False

    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    return ip in (ipaddress.IPv4Address("127.0.0.1"), ipaddress.IPv6Address("::1"))


def _split_host(val: str) -> tuple[str, int | None] | None:
    if val.startswith("["):
        literal, close, after = val[1:].partition("]")

        if not close:
            return None

        host, port = f"[{literal}]", None

        if after:
            if not after.startswith(":"):
                return None
            port = after[1:]
    else:
        host, colon, raw = val.partition(":")
        port = raw if colon else None

    if port is not None and (
        not port.isascii() or not port.isdigit() or port.startswith("0") or int(port) > 65_535
    ):
        return None

    return (host.lower(), None if port is None else int(port)) if host else None


def _addr(scope: Scope, key: str) -> tuple[object, object]:
    val = scope.get(key)

    if isinstance(val, list | tuple) and len(val) == 2:
        return val[0], val[1]

    return None, None


def _headers(scope: Scope) -> list[tuple[str, str]]:
    raw = scope.get("headers")
    out = []

    if isinstance(raw, Iterable):
        for pair in raw:
            k, v = pair
            out.append((bytes(k).decode("latin-1").lower(), bytes(v).decode("latin-1")))

    return out


def _one(headers: list[tuple[str, str]], name: str) -> str | None:
    vals = [v for k, v in headers if k == name]
    return vals[0] if len(vals) == 1 else None


def _public_hosts(names: Iterable[str]) -> frozenset[str]:
    out = set()

    for name in names:
        lower = name.lower()

        if not _PUBLIC_HOST.fullmatch(lower):
            raise ConfigError("ACLP public hosts must be plain host names")

        out.add(lower)

    return frozenset(out)


def _discovery_document(
    callbacks: Mapping[str, Callback[Never]], discovery: Discovery, authorized: bool
) -> bytes:
    events = sorted(callbacks)
    doc: dict[str, object] = {
        "endpoint": discovery.endpoint,
        "auth": discovery.auth
        if discovery.auth is not None
        else {"methods": ["token"] if authorized else []},
        "events": events,
        "requests": [m for m in events if callbacks[m].result is not None],
    }

    if discovery.name is not None:
        doc["name"] = discovery.name

    if not is_discovery_document(doc):
        raise ConfigError("ACLP discovery document is invalid")

    return encode_json(doc)


def create_app(
    callbacks: Mapping[str, Callback[Never]],
    *,
    authorization: str | None = None,
    hosts: Iterable[str] = (),
    discovery: Discovery | None = None,
    on_error: Callable[[CallbackError], None] | None = None,
) -> ASGIApp:
    """Build an ASGI application that serves ACLP callbacks over HTTP.

    The app validates every message before a callback runs and checks each request result
    against its `ResultSchema`. It is loopback-only unless `hosts` names public host names,
    which require `authorization`, the exact `Authorization` header value to accept. At most
    32 callbacks run at once; a slot stays reserved until its callback completes. A notification
    is answered 202 on admission and its callback runs afterwards in the same ASGI task, so the
    ASGI server's graceful shutdown waits for it. Callback failures go to `on_error`; without
    it they are discarded, because the library does not log on its own.

    Connection, header-size and keep-alive limits belong to the ASGI server; run it with a
    bounded connection count, for example `uvicorn --limit-concurrency`. The app keeps its
    state on one event loop and is not thread-safe.

    Raises `ConfigError` for an unknown method, an `authorization` value that is not an HTTP
    scheme and a single-line credential, invalid or unauthorized public hosts, or an invalid
    discovery document.
    """
    for method in callbacks:
        if not is_event_method(method):
            raise ConfigError(f"ACLP callbacks name an unknown method: {method}")

    scheme = None

    if authorization is not None:
        match = _SCHEME.fullmatch(authorization)

        if match is None:
            raise ConfigError("authorization must contain an HTTP scheme and credential")

        scheme = match.group(1)

    named = _public_hosts(hosts)

    if named and authorization is None:
        raise ConfigError("ACLP public hosts require authorization")

    warm()

    return _App(
        callbacks=dict(callbacks),
        credential=None
        if authorization is None
        else hashlib.sha256(authorization.encode()).digest(),
        scheme=scheme,
        named=named,
        doc=None
        if discovery is None
        else _discovery_document(callbacks, discovery, authorization is not None),
        on_error=on_error,
    )


async def _respond(
    send: Send, status: int, body: bytes = b"", extra: Iterable[tuple[bytes, bytes]] = ()
) -> None:
    headers = [(b"content-length", str(len(body)).encode()), *extra]

    if body:
        headers.append((b"content-type", b"application/json"))

    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def _rpc_error(send: Send, status: int, id_: str | None, code: int, message: str) -> None:
    body = encode_json({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})
    await _respond(send, status, body)


async def _invalid(send: Send, id_: str | None, code: int, message: str) -> None:
    if id_ is None:
        await _respond(send, 400)
    else:
        await _rpc_error(send, 200, id_, code, message)


async def _read_body(receive: Receive) -> bytes:
    body = bytearray()

    try:
        async with asyncio.timeout(READ_TIMEOUT):
            while True:
                msg = await receive()

                if msg.get("type") == "http.disconnect":
                    raise _Reject(400)

                chunk = msg.get("body", b"")
                body += chunk if isinstance(chunk, bytes) else b""

                if len(body) > MAX_BODY_BYTES:
                    raise _Reject(413)

                if not msg.get("more_body", False):
                    return bytes(body)
    except TimeoutError as err:
        raise _Reject(408) from err


async def _run(cb: Callback[Never], params: dict[str, object], ctx: CallContext) -> object:
    handle = cast("Callable[[dict[str, object], CallContext], object]", cb.handle)

    if inspect.iscoroutinefunction(handle):
        return await handle(params, ctx)

    res = await asyncio.to_thread(handle, params, ctx)
    return await res if inspect.isawaitable(res) else res


async def _lifespan(receive: Receive, send: Send) -> None:
    while True:
        msg = await receive()

        if msg.get("type") == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif msg.get("type") == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


@dataclass(slots=True)
class _App:
    callbacks: dict[str, Callback[Never]]
    credential: bytes | None
    scheme: str | None
    named: frozenset[str]
    doc: bytes | None
    on_error: Callable[[CallbackError], None] | None
    active: int = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            await self._http(scope, receive, send)
        elif scope.get("type") == "lifespan":
            await _lifespan(receive, send)

    def _report(self, err: CallbackError) -> None:
        if self.on_error is not None:
            self.on_error(err)

    def _validate_target(self, scope: Scope, headers: list[tuple[str, str]]) -> None:
        host = _one(headers, "host")
        parsed = None if host is None else _split_host(host)

        if parsed is None:
            raise _Reject(403)

        name, port = parsed

        if name not in self.named:
            peer, _ = _addr(scope, "client")
            local, local_port = _addr(scope, "server")

            if name not in _LOOPBACK_NAMES or (port or 80) != local_port:
                raise _Reject(403)

            if not (_loopback(peer) and _loopback(local)):
                raise _Reject(403)

        raw = scope.get("raw_path")
        path = (
            bytes(raw)
            if isinstance(raw, bytes | bytearray)
            else str(scope.get("path", "")).encode()
        )

        if (
            not path.startswith(b"/")
            or path.startswith(b"//")
            or any(k == "origin" for k, _ in headers)
        ):
            raise _Reject(403)

    def _validate_call(self, scope: Scope, headers: list[tuple[str, str]]) -> None:
        if self.credential is not None:
            supplied = [v for k, v in headers if k == "authorization"]
            digest = hashlib.sha256((supplied[0] if supplied else "").encode("latin-1")).digest()

            if len(supplied) != 1 or not hmac.compare_digest(self.credential, digest):
                raise _Reject(401)

        if scope.get("method") != "POST":
            raise _Reject(405)

        kind = _one(headers, "content-type")

        if kind is None or kind.split(";", 1)[0].strip().lower() != "application/json":
            raise _Reject(415)

        for k, v in headers:
            if k == "content-length" and not (
                v.strip().isascii() and v.strip().isdigit() and int(v) <= MAX_BODY_BYTES
            ):
                raise _Reject(413)

    async def _dispatch(self, send: Send, msg: dict[str, object], ctx: CallContext) -> None:
        method = cast("str", msg["method"])
        params = cast("dict[str, object]", msg["params"])
        id_ = request_id(msg)

        if not is_event_method(method):
            await _invalid(send, id_, -32601, "Method not found")
            return

        cb = self.callbacks.get(method)

        if cb is None or (id_ is not None and cb.result is None):
            await _invalid(send, id_, -32601, "Method not found")
            return

        if not validate_params(method, params):
            await _invalid(send, id_, -32602, "Invalid params")
            return

        if id_ is None:
            await _respond(send, 202)
            await self._notify(cb, method, params, ctx)
            return

        await self._request(send, cb, method, params, ctx, id_)

    async def _notify(
        self, cb: Callback[Never], method: str, params: dict[str, object], ctx: CallContext
    ) -> None:
        try:
            await _run(cb, params, ctx)
        except Exception as err:  # noqa: BLE001  # a callback is caller code; its failure is a diagnostic
            self._report(_failure(method, "failed", err))

    async def _request(
        self,
        send: Send,
        cb: Callback[Never],
        method: str,
        params: dict[str, object],
        ctx: CallContext,
        id_: str,
    ) -> None:
        try:
            val = await _run(cb, params, ctx)
        except Exception as err:  # noqa: BLE001  # a callback is caller code; its failure is a diagnostic
            self._report(_failure(method, "failed", err))
            await _rpc_error(send, 200, id_, -32603, "Internal error")
            return

        body = None

        if cb.result is not None and cb.result.validate(val):
            try:
                body = encode_json({"jsonrpc": "2.0", "id": id_, "result": val})
            except JsonError:
                body = None

        if body is None:
            self._report(
                CallbackError(method, "returned a result that does not satisfy its schema")
            )
            await _rpc_error(send, 200, id_, -32603, "Internal error")
            return

        await _respond(send, 200, body)

    async def _admit(self, receive: Receive, send: Send, headers: list[tuple[str, str]]) -> None:
        body = await _read_body(receive)

        try:
            msg = decode_json(body)
        except JsonError:
            await _rpc_error(send, 400, None, -32700, "Parse error")
            return

        if not is_envelope(msg):
            if is_notification(msg):
                await _respond(send, 400)
            else:
                await _rpc_error(send, 400, request_id(msg), -32600, "Invalid request")
            return

        await self._dispatch(send, msg, CallContext(_one(headers, "aclp-client")))

    async def _http(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = _headers(scope)
        reserved = False

        try:
            self._validate_target(scope, headers)

            if scope.get("method") == "GET" and scope.get("path") == DISCOVERY_PATH:
                await (_respond(send, 404) if self.doc is None else _respond(send, 200, self.doc))
                return

            self._validate_call(scope, headers)

            if self.active >= MAX_ACTIVE_CALLBACKS:
                raise _Reject(429)

            self.active += 1
            reserved = True
            await self._admit(receive, send, headers)
        except _Reject as rej:
            await self._reject(send, rej.status)
        finally:
            if reserved:
                self.active -= 1

    async def _reject(self, send: Send, status: int) -> None:
        extra = [(b"connection", b"close")]

        if status == 401 and self.scheme is not None:
            extra.append((b"www-authenticate", f'{self.scheme} realm="aclp"'.encode()))

        if status == 405:
            extra.append((b"allow", b"POST"))

        await _respond(send, status, extra=extra)


def _failure(method: str, reason: str, cause: Exception) -> CallbackError:
    err = CallbackError(method, reason)
    err.__cause__ = cause
    return err
