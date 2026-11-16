import ipaddress
import re
from collections.abc import Iterable

from aclp._errors import SchemaError
from aclp._schema import compile_local

_UNSTRUCTURED = frozenset(
    {"schema", "inputSchema", "outputSchema", "arguments", "structuredContent", "value", "data"}
)

_BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

_HOST = re.compile(r"[A-Za-z0-9\-._~!$&'()*+,;=%]+")


def _unique(items: Iterable[object], key: str) -> bool:
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            return False

        if key not in item:
            continue

        identity = repr(item[key])

        if identity in seen:
            return False

        seen.add(identity)

    return True


def _unique_in(params: dict[str, object], name: str, key: str) -> bool:
    items = params.get(name)
    return isinstance(items, list) and _unique(items, key)


def canonical_base64(data: str) -> bool:
    """Whether `data` is base64 with valid padding and zero padding bits.

    >>> canonical_base64("AA==")
    True
    >>> canonical_base64("AB==")
    False
    """
    if len(data) % 4:
        return False

    body = data.rstrip("=")
    padding = len(data) - len(body)

    if any(c not in _BASE64 for c in body):
        return False

    if padding == 0 or not body:
        return padding == 0

    last = _BASE64.index(body[-1])

    if padding == 1:
        return last & 0b11 == 0

    if padding == 2:
        return last & 0b1111 == 0

    return False


def network_origin(origin: str) -> bool:
    """Whether `origin` is an HTTP(S) origin: scheme, host and optional port, nothing else.

    >>> network_origin("https://example.com:8443/")
    True
    >>> network_origin("https://user@example.com")
    False
    """
    lower = origin.lower()

    if lower.startswith("https://"):
        rest = origin[8:]
    elif lower.startswith("http://"):
        rest = origin[7:]
    else:
        return False

    authority = rest.removesuffix("/")

    if not authority or any(c in authority for c in "/?#\\@"):
        return False

    if authority.startswith("["):
        host, close, after = authority[1:].partition("]")

        if not close or (after and not after.startswith(":")):
            return False

        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            return False

        port = after[1:] if after else None
    else:
        host, colon, raw = authority.partition(":")
        port = raw if colon else None

        if not _HOST.fullmatch(host):
            return False

    if port is not None and not (port.isascii() and port.isdigit() and int(port) <= 65_535):
        return False

    return bool(host)


def _embedded(schema: object) -> bool:
    try:
        compile_local(schema)
    except SchemaError:
        return False

    return True


def _content(val: object) -> bool:
    if isinstance(val, list):
        return all(_content(v) for v in val)

    if not isinstance(val, dict):
        return True

    kind = val.get("kind")
    data = val.get("data")
    origin = val.get("origin")

    if (
        val.get("type") in ("image", "audio")
        and isinstance(data, str)
        and not canonical_base64(data)
    ):
        return False

    if kind == "network" and isinstance(origin, str) and not network_origin(origin):
        return False

    for key in ("inputSchema", "outputSchema"):
        if key in val and not _embedded(val[key]):
            return False

    if kind == "form" and not _embedded(val.get("schema")):
        return False

    for key, child in val.items():
        if key in _UNSTRUCTURED:
            continue

        blob = child.get("blob") if isinstance(child, dict) else None

        if key == "resource" and isinstance(blob, str) and not canonical_base64(blob):
            return False

        if not _content(child):
            return False

    return True


def _accepted_form(params: dict[str, object]) -> bool:
    interaction = params.get("interaction")
    response = params.get("response")

    if not (isinstance(interaction, dict) and isinstance(response, dict)):
        return True

    if interaction.get("kind") != "form" or response.get("status") != "accepted":
        return True

    try:
        return compile_local(interaction.get("schema")).is_valid(response.get("value"))
    except SchemaError:
        return False


def validate_semantics(method: str, params: object) -> bool:
    """Apply the protocol's cross-field rules that JSON Schema cannot express."""
    if not isinstance(params, dict) or not _content(params):
        return False

    if method == "catalog.changed":
        return _unique_in(params, "entries", "name")

    if method == "permission.requested":
        return _unique_in(params, "options", "id")

    if method == "plan.updated":
        return _unique_in(params, "steps", "id")

    if method == "configuration.changed":
        return _unique_in(params, "changes", "key")

    if method == "tool.batch.finished":
        calls = params.get("calls")
        return isinstance(calls, list) and _unique(
            (c.get("call") if isinstance(c, dict) else None for c in calls), "id"
        )

    if method == "interaction.resolved":
        return _accepted_form(params)

    return True
