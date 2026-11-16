import json
import math

from aclp._errors import JsonError

MAX_BODY_BYTES = 1_048_576

# The root has depth zero; each nested value adds one level.
MAX_JSON_DEPTH = 64

# Count containers and scalar values once each; object keys do not count.
MAX_JSON_NODES = 100_000


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj = dict(pairs)

    if len(obj) != len(pairs):
        raise JsonError("duplicate JSON object key")

    return obj


def _finite(val: str) -> float:
    x = float(val)

    if not math.isfinite(x):
        raise JsonError("non-finite JSON number")

    return x


def _constant(val: str) -> object:
    raise JsonError(f"invalid JSON constant {val}")


def _utf8(val: str) -> None:
    if not val.isascii():
        val.encode("utf-8")


def check_bounds(val: object) -> None:
    """Raise `JsonError` unless `val` is finite, acyclic JSON within the depth and node bounds."""
    nodes = 0
    stack: list[tuple[object, int]] = [(val, 0)]

    while stack:
        x, depth = stack.pop()
        nodes += 1

        if depth > MAX_JSON_DEPTH or nodes > MAX_JSON_NODES:
            raise JsonError("JSON complexity limit exceeded")

        if x is None or isinstance(x, bool | int):
            continue

        if isinstance(x, float):
            if not math.isfinite(x):
                raise JsonError("non-finite JSON number")
            continue

        if isinstance(x, str):
            _utf8(x)
            continue

        if isinstance(x, list | tuple):
            stack.extend((v, depth + 1) for v in x)
            continue

        if isinstance(x, dict):
            for k, v in x.items():
                if not isinstance(k, str):
                    raise JsonError("JSON object keys must be strings")
                _utf8(k)
                stack.append((v, depth + 1))
            continue

        raise JsonError(f"{type(x).__name__} is not a JSON value")


def decode_json(body: bytes) -> object:
    """Decode one strict JSON value: UTF-8, unique keys, finite numbers, bounded size and nesting.

    >>> decode_json(b'{"a": [1, 2.5, null]}')
    {'a': [1, 2.5, None]}
    >>> decode_json(b'{"a": 1, "a": 2}')
    Traceback (most recent call last):
    ...
    aclp.JsonError: duplicate JSON object key
    """
    if len(body) > MAX_BODY_BYTES:
        raise JsonError("JSON body exceeds 1 MiB")

    try:
        text = body.decode("utf-8")
        val: object = json.loads(
            text,
            object_pairs_hook=_unique,
            parse_float=_finite,
            parse_constant=_constant,
        )
    except JsonError:
        raise
    except (UnicodeError, RecursionError, ValueError) as err:
        raise JsonError("invalid JSON") from err

    try:
        check_bounds(val)
    except UnicodeError as err:
        raise JsonError("JSON string is not valid Unicode") from err

    return val


def encode_json(val: object) -> bytes:
    """Encode `val` as compact UTF-8 JSON that any ACLP peer can decode back.

    >>> encode_json({"jsonrpc": "2.0", "params": {}})
    b'{"jsonrpc":"2.0","params":{}}'
    """
    try:
        check_bounds(val)
    except UnicodeError as err:
        raise JsonError("JSON string is not valid Unicode") from err

    body = json.dumps(val, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()

    if len(body) > MAX_BODY_BYTES:
        raise JsonError("JSON body exceeds 1 MiB")

    return body
