"""Client and callback server for the Agent Context Lifecycle Protocol (ACLP).

`Client` and `AsyncClient` send typed lifecycle events to a server as JSON-RPC requests or
notifications over HTTP. `create_app` builds an ASGI application that validates each message
against the pinned protocol schema, runs the matching `Callback` and checks request results
against their `ResultSchema`. Event parameter types live in `aclp.events`.

Everything outside `__all__` and `aclp.events` is private, even when it can be imported.
"""

from aclp._async_client import DISCOVERY_PATH, AsyncClient, discover_async
from aclp._errors import (
    AclpError,
    AuthorizationError,
    CallbackError,
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
    SchemaError,
    StatusError,
    TransportError,
)
from aclp._json import MAX_BODY_BYTES, decode_json, encode_json
from aclp._on_error import FAIL_CLOSED_METHODS, OnError, on_error_for
from aclp._result import ResultSchema
from aclp._server import ASGIApp, Callback, CallContext, Discovery, create_app
from aclp._sync_client import Client, discover
from aclp._validation import is_event_method, validate_params

__all__ = [
    "DISCOVERY_PATH",
    "FAIL_CLOSED_METHODS",
    "MAX_BODY_BYTES",
    "ASGIApp",
    "AclpError",
    "AsyncClient",
    "AuthorizationError",
    "CallContext",
    "Callback",
    "CallbackError",
    "CapacityError",
    "Client",
    "ClientError",
    "ClosedError",
    "ConfigError",
    "DeadlineError",
    "Discovery",
    "DiscoveryError",
    "FlushError",
    "InvalidParamsError",
    "InvalidResponseError",
    "InvalidResultError",
    "JsonError",
    "NotConsentedError",
    "OnError",
    "ResultSchema",
    "RpcError",
    "SchemaError",
    "StatusError",
    "TransportError",
    "create_app",
    "decode_json",
    "discover",
    "discover_async",
    "encode_json",
    "is_event_method",
    "on_error_for",
    "validate_params",
]
