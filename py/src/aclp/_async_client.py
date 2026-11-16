import math
import ssl
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from types import TracebackType
from typing import Self, TypeVar

from aclp import _async_io as io
from aclp._async_http import exchange
from aclp._endpoint import client_header, header_value, parse_endpoint
from aclp._errors import (
    AuthorizationError,
    CapacityError,
    ClientError,
    ClosedError,
    ConfigError,
    DeadlineError,
    DiscoveryError,
    FlushError,
    InvalidParamsError,
    InvalidResponseError,
    InvalidResultError,
    JsonError,
    NotConsentedError,
    RpcError,
    StatusError,
)
from aclp._http import Reply
from aclp._json import decode_json, encode_json
from aclp._on_error import OnError, on_error_for
from aclp._result import ResultSchema
from aclp._validation import is_client_info, is_discovery_document, is_response, validate_params
from aclp.events import ClientInfo, DiscoveryDocument, EventMethod

T = TypeVar("T")

MAX_PENDING = 64

MAX_TIMEOUT = 2_147_483.647

DISCOVERY_PATH = "/.well-known/aclp"


def _tls(ca: str | None) -> ssl.SSLContext:
    ctx = ssl.create_default_context()

    if ca is not None:
        try:
            ctx.load_verify_locations(cadata=ca)
        except (ssl.SSLError, ValueError) as err:
            raise ConfigError("ACLP CA bundle has no usable PEM certificate") from err

    return ctx


def _timeout(val: float) -> float:
    if not (math.isfinite(val) and 0 < val <= MAX_TIMEOUT):
        raise ConfigError("ACLP timeout must be positive and at most 2147483.647 seconds")

    return val


class AsyncClient:
    """Sends ACLP lifecycle events to one callback server over HTTP or HTTPS.

    Use it as `async with AsyncClient(url) as client:` so `close()` runs on exit. The async
    client delivers notifications in tasks owned by that context and needs it open to notify;
    the sync client delivers each notification before `notify` returns. Requests are never
    retried or redirected, and each call uses its own HTTP/1.1 connection. An instance is not
    thread-safe; the async client also belongs to one event loop.

    `timeout` is the per-call deadline in seconds; it starts before local validation and covers
    the authorization provider. `authorization` is the exact `Authorization` header value, or a
    callable that computes it before every call. `client` identifies the client and harness in
    the `ACLP-Client` header. `events` limits sends to the methods the user consented to;
    `client.*` methods are always allowed. `ca` adds PEM certificates to the system trust store.
    `failure_policy` sets the `OnError` of every method; `on_error` receives each notification
    delivery failure. Raises `ConfigError` for an invalid URL, timeout, identity or CA bundle.
    """

    __module__ = "aclp"

    def __init__(
        self,
        url: str,
        *,
        authorization: io.Authorization | None = None,
        timeout: float = 5.0,
        client: ClientInfo | None = None,
        events: Iterable[str] | None = None,
        ca: str | None = None,
        failure_policy: OnError | None = None,
        on_error: Callable[[ClientError], None] | None = None,
    ) -> None:
        self._endpoint = parse_endpoint(url)
        self._timeout = _timeout(timeout)

        if isinstance(authorization, str) and not header_value(authorization):
            raise ConfigError("ACLP authorization must be a valid HTTP header value")

        if client is not None and not is_client_info(client):
            raise ConfigError("ACLP client identity does not match ClientInfo")

        identity = None if client is None else client_header(client)

        if identity is not None and not header_value(identity):
            raise ConfigError("ACLP client identity must be printable ASCII")

        self._auth = authorization
        self._identity = identity
        self._events = None if events is None else frozenset(events)
        self._ssl = _tls(ca) if self._endpoint.tls else None
        self._policy = failure_policy
        self._on_error = on_error
        self._pending = io.Pending()
        self._failures: list[ClientError] = []
        self._active = 0
        self._closed = False

    async def __aenter__(self) -> Self:
        if self._closed:
            raise ClosedError("ACLP client is closed")

        await self._pending.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def failure_policy(self, method: str) -> OnError:
        """What a failed request for `method` does to the continuation it guards.

        The configured `failure_policy`, else `on_error_for(method)`.
        """
        return on_error_for(method, self._policy)

    @contextmanager
    def _slot(self) -> Iterator[None]:
        if self._closed:
            raise ClosedError("ACLP client is closed")

        if self._active >= MAX_PENDING:
            raise CapacityError("ACLP client capacity exhausted")

        self._active += 1

        try:
            yield
        finally:
            self._active -= 1

    def _prepare(self, method: str, params: Mapping[str, object], id_: str | None) -> bytes:
        if (
            self._events is not None
            and method not in self._events
            and not method.startswith("client.")
        ):
            raise NotConsentedError(method)

        msg: dict[str, object] = {"jsonrpc": "2.0", "method": method, "params": params}

        if id_ is not None:
            msg["id"] = id_

        try:
            body = encode_json(msg)
        except JsonError as err:
            raise InvalidParamsError(method) from err

        if not validate_params(method, params):
            raise InvalidParamsError(method)

        return body

    async def _post(self, body: bytes, deadline: float) -> Reply:
        headers = [("Content-Type", "application/json")]

        if self._auth is not None:
            auth = await io.authorize(self._auth, deadline)

            if not header_value(auth):
                raise AuthorizationError(
                    "ACLP authorization provider returned an invalid header value"
                )

            headers.append(("Authorization", auth))

        if self._identity is not None:
            headers.append(("ACLP-Client", self._identity))

        return await exchange(self._endpoint, self._ssl, "POST", headers, body, deadline)

    async def request(
        self, method: EventMethod, params: Mapping[str, object], result: ResultSchema[T]
    ) -> T:
        """Send a request and return its result once it matches `result`.

        The deadline covers validation, the HTTP exchange and result checking. Raises a
        `ClientError` subclass for local capacity or validation failures, transport failures,
        the deadline, a non-JSON-RPC or mismatched reply, a callback error, or a result outside
        `result`; apply `failure_policy(method)` to the continuation the request guards.
        """
        deadline = time.monotonic() + self._timeout
        id_ = str(uuid.uuid4())

        with self._slot():
            body = self._prepare(method, params, id_)
            reply = await self._post(body, deadline)

        if reply.status != 200:
            raise StatusError(reply.status)

        if not reply.json:
            raise InvalidResponseError("ACLP result requires Content-Type application/json")

        try:
            msg = decode_json(reply.body)
        except JsonError as err:
            raise InvalidResponseError("invalid ACLP response") from err

        if not is_response(msg) or msg["id"] != id_:
            raise InvalidResponseError("invalid or mismatched ACLP response")

        rpc = msg.get("error")

        if isinstance(rpc, dict):
            raise RpcError(rpc["code"], rpc["message"])

        val = msg["result"]

        if not result.validate(val):
            raise InvalidResultError("ACLP callback result does not match its installed schema")

        if time.monotonic() >= deadline:
            raise DeadlineError("ACLP request deadline exceeded")

        return val

    def notify(self, method: EventMethod, params: Mapping[str, object]) -> None:
        """Validate a notification and hand it to delivery.

        Raises `CapacityError`, `NotConsentedError`, `InvalidParamsError` or `ClosedError`
        before anything is sent. Delivery failures reach `on_error` and the next `flush()`.
        """
        deadline = time.monotonic() + self._timeout

        if not self._pending.ready():
            raise ClosedError("AsyncClient.notify requires `async with AsyncClient(...)`")

        with self._slot():
            body = self._prepare(method, params, None)
            self._active += 1

        self._pending.start(self._deliver, body, deadline)

    async def _deliver(self, body: bytes, deadline: float) -> None:
        try:
            reply = await self._post(body, deadline)

            if reply.status != 202 or reply.body:
                raise StatusError(reply.status)
        except ClientError as err:
            if self._on_error is not None:
                self._on_error(err)

            if len(self._failures) < MAX_PENDING:
                self._failures.append(err)
        finally:
            self._active -= 1

    async def flush(self) -> None:
        """Wait for every outstanding notification admission attempt.

        Success confirms server admission, not callback completion. Raises `FlushError` with
        the delivery failures recorded since the previous flush.
        """
        await self._pending.wait()

        failures, self._failures = self._failures, []

        if failures:
            raise FlushError(failures)

    async def close(self) -> None:
        """Stop accepting calls and wait for outstanding notification deliveries."""
        self._closed = True
        await self._pending.close()


async def discover_async(
    url: str, *, timeout: float = 5.0, ca: str | None = None
) -> DiscoveryDocument:
    """Fetch and check the discovery document at `url`'s origin, `/.well-known/aclp`.

    Raises `ConfigError` for an invalid URL, timeout or CA bundle, and a `ClientError`
    subclass for transport failures, a non-200 or non-JSON reply, or an invalid document.
    """
    ep = parse_endpoint(url).with_path(DISCOVERY_PATH)
    ctx = _tls(ca) if ep.tls else None
    deadline = time.monotonic() + _timeout(timeout)
    reply = await exchange(ep, ctx, "GET", [("Accept", "application/json")], b"", deadline)

    if reply.status != 200:
        raise StatusError(reply.status)

    if not reply.json:
        raise InvalidResponseError("ACLP discovery requires Content-Type application/json")

    try:
        doc = decode_json(reply.body)
    except JsonError as err:
        raise DiscoveryError("invalid ACLP discovery document") from err

    if not is_discovery_document(doc):
        raise DiscoveryError("invalid ACLP discovery document")

    return doc
