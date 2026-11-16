from collections.abc import Sequence


class AclpError(Exception):
    """Base class for every error this package raises.

    `str()` of any `AclpError` is safe to log: it never contains a request body, a credential
    or callback content.
    """

    __module__ = "aclp"


class JsonError(AclpError, ValueError):
    """A body or value outside strict, bounded JSON."""

    __module__ = "aclp"


class SchemaError(AclpError, ValueError):
    """A JSON Schema that cannot be installed as a local Draft-07 schema."""

    __module__ = "aclp"


class ConfigError(AclpError, ValueError):
    """Invalid client or server configuration, detected before any I/O."""

    __module__ = "aclp"


class ClientError(AclpError):
    """A failed request, notification admission attempt or local delivery precondition.

    A failed request's guarded continuation follows the client's failure policy: `deny` keeps it
    blocked, `allow` lets it proceed as if the result carried no effects.
    """

    __module__ = "aclp"


class CapacityError(ClientError):
    """64 requests or notification attempts are already outstanding."""

    __module__ = "aclp"


class InvalidParamsError(ClientError):
    """The parameters do not satisfy the event's schema or semantic rules."""

    __module__ = "aclp"

    def __init__(self, method: str) -> None:
        super().__init__(f"invalid ACLP parameters for {method}")
        self.method = method


class NotConsentedError(ClientError):
    """The method is outside the events the user consented to share."""

    __module__ = "aclp"

    def __init__(self, method: str) -> None:
        super().__init__(f"ACLP method {method} is not consented")
        self.method = method


class ClosedError(ClientError):
    """The client is closed, or an `AsyncClient` notification was sent outside `async with`."""

    __module__ = "aclp"


class AuthorizationError(ClientError):
    """The authorization provider failed or returned a value that cannot be an HTTP header."""

    __module__ = "aclp"


class DeadlineError(ClientError):
    """The deadline passed before a valid reply was received and checked."""

    __module__ = "aclp"


class TransportError(ClientError):
    """The connection failed, closed early, or the server sent malformed HTTP."""

    __module__ = "aclp"


class StatusError(ClientError):
    """A request did not receive HTTP 200, or a notification an empty HTTP 202."""

    __module__ = "aclp"

    def __init__(self, status: int) -> None:
        super().__init__(f"ACLP call was not accepted (HTTP {status})")
        self.status = status


class InvalidResponseError(ClientError):
    """The reply is not JSON, not valid JSON-RPC, too large, or does not echo the request id."""

    __module__ = "aclp"


class RpcError(ClientError):
    """The callback answered with a JSON-RPC error.

    `message` holds the server's text; `str()` names only the code, because the server chose
    that text and it may echo request content.
    """

    __module__ = "aclp"

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"ACLP callback failed with JSON-RPC error {code}")
        self.code = code
        self.message = message


class InvalidResultError(ClientError):
    """The result does not match the installed result schema."""

    __module__ = "aclp"


class DiscoveryError(ClientError):
    """The discovery response is not a valid `DiscoveryDocument`."""

    __module__ = "aclp"


class FlushError(ExceptionGroup[ClientError], AclpError):
    """Notification deliveries that failed since the previous flush, oldest first, at most 64."""

    __module__ = "aclp"

    def __new__(cls, failures: Sequence[ClientError]) -> "FlushError":
        return super().__new__(cls, "ACLP notification delivery failed", list(failures))

    def __init__(self, failures: Sequence[ClientError]) -> None:
        super().__init__("ACLP notification delivery failed", list(failures))

    def derive(self, excs: Sequence[ClientError]) -> "FlushError":  # type: ignore[override]  # split() passes a narrower sequence
        return FlushError(excs)


class CallbackError(AclpError):
    """A server-side callback failure after admission, passed to the server's `on_error` hook.

    Requests answer it with JSON-RPC `-32603`; the detail never reaches the caller.
    """

    __module__ = "aclp"

    def __init__(self, method: str, reason: str) -> None:
        super().__init__(f"ACLP callback for {method} {reason}")
        self.method = method
