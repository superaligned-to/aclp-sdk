import functools
import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import TypeGuard
from urllib.parse import urlsplit

from jsonschema import Draft7Validator
from referencing import Registry

from aclp._errors import JsonError
from aclp._json import check_bounds
from aclp._methods import PARAMS
from aclp._schema import FORMATS
from aclp._semantics import validate_semantics
from aclp.events import ClientInfo, DiscoveryDocument, EventMethod

MAX_ID_BYTES = 128


@dataclass(frozen=True, slots=True)
class _Validators:
    envelope: Draft7Validator
    response: Draft7Validator
    discovery: Draft7Validator
    client: Draft7Validator
    params: dict[str, Draft7Validator]


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/definitions/{name}"}


@functools.cache
def _validators() -> _Validators:
    root = json.loads(files("aclp").joinpath("schema.json").read_bytes())

    def compile_(*refs: Mapping[str, object]) -> Draft7Validator:
        schema = {k: v for k, v in root.items() if k != "oneOf"}
        schema["allOf"] = list(refs)
        return Draft7Validator(schema, format_checker=FORMATS, registry=Registry())

    return _Validators(
        envelope=compile_(_ref("InvocationEnvelope")),
        response=compile_({"oneOf": [_ref("SuccessResponse"), _ref("ErrorResponse")]}),
        discovery=compile_(_ref("DiscoveryDocument")),
        client=compile_(_ref("ClientInfo")),
        params={m: compile_(_ref(d)) for m, d in PARAMS.items()},
    )


def warm() -> None:
    """Compile the protocol validators now rather than on the first message."""
    _validators()


def _json_value(val: object) -> bool:
    try:
        check_bounds(val)
    except (JsonError, UnicodeError):
        return False

    return True


def _bounded_id(val: dict[str, object]) -> bool:
    id_ = val.get("id")
    return id_ is None or (isinstance(id_, str) and len(id_.encode()) <= MAX_ID_BYTES)


def is_envelope(val: object) -> TypeGuard[dict[str, object]]:
    """Whether `val` is a JSON-RPC request or notification envelope for any method."""
    return (
        isinstance(val, dict)
        and _json_value(val)
        and _bounded_id(val)
        and _validators().envelope.is_valid(val)
    )


def is_response(val: object) -> TypeGuard[dict[str, object]]:
    """Whether `val` is a JSON-RPC success or error reply."""
    return (
        isinstance(val, dict)
        and _json_value(val)
        and _bounded_id(val)
        and _validators().response.is_valid(val)
    )


def is_event_method(method: str) -> TypeGuard[EventMethod]:
    """Whether `method` names one of the standard events.

    >>> is_event_method("input.submitted"), is_event_method("rpc.discover")
    (True, False)
    """
    return method in PARAMS


def validate_params(method: str, params: object) -> bool:
    """Whether `params` satisfy the schema and semantic rules of the event `method`.

    >>> validate_params("session.started", {"sessionId": "session-1"})
    True
    >>> validate_params("session.started", {})
    False
    """
    validator = _validators().params.get(method)

    return (
        validator is not None
        and _json_value(params)
        and validator.is_valid(params)
        and validate_semantics(method, params)
    )


def request_id(val: object) -> str | None:
    if not isinstance(val, dict):
        return None

    id_ = val.get("id")

    if isinstance(id_, str) and id_ and len(id_.encode()) <= MAX_ID_BYTES:
        return id_

    return None


def is_notification(val: object) -> bool:
    if not isinstance(val, dict):
        return False

    method = val.get("method")
    return (
        val.get("jsonrpc") == "2.0" and isinstance(method, str) and bool(method) and "id" not in val
    )


def http_endpoint(url: str) -> bool:
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018  # urlsplit validates the port lazily
    except ValueError:
        return False

    return (
        parts.scheme in ("http", "https")
        and bool(parts.hostname)
        and "@" not in parts.netloc
        and "#" not in url
    )


def is_discovery_document(val: object) -> TypeGuard[DiscoveryDocument]:
    """Whether `val` is a valid discovery document whose `requests` are a subset of `events`."""
    if not (isinstance(val, dict) and _json_value(val)):
        return False

    if not _validators().discovery.is_valid(val):
        return False

    endpoint = val["endpoint"]
    events = set(val["events"])
    return (
        isinstance(endpoint, str) and http_endpoint(endpoint) and events.issuperset(val["requests"])
    )


def is_client_info(val: object) -> TypeGuard[ClientInfo]:
    """Whether `val` is a valid `ClientInfo`."""
    return _json_value(val) and _validators().client.is_valid(val)
