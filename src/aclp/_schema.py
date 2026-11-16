from collections.abc import Iterator

from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import SchemaError as InvalidSchema
from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT7

from aclp._errors import JsonError, SchemaError
from aclp._json import check_bounds
from aclp._uri import is_uri

# Count schema containers and scalar values, including annotation data; exclude object keys.
MAX_SCHEMA_NODES = 2_048

MAX_SCHEMA_DEPTH = 32

DRAFT_07 = frozenset(
    {
        "http://json-schema.org/draft-07/schema#",
        "http://json-schema.org/draft-07/schema",
        "https://json-schema.org/draft-07/schema#",
        "https://json-schema.org/draft-07/schema",
    }
)

# Only formats whose checkers ship with jsonschema itself, so results do not depend on which
# optional packages happen to be installed; `uri` uses the RFC 3986 check in this package.
FORMATS = FormatChecker(formats=("date", "email", "idn-email", "ipv4", "ipv6", "regex", "uuid"))

FORMATS.checks("uri")(lambda x: not isinstance(x, str) or is_uri(x))


def _complexity(schema: object) -> None:
    nodes = 0
    stack: list[tuple[object, int]] = [(schema, 0)]

    while stack:
        x, depth = stack.pop()
        nodes += 1

        if nodes > MAX_SCHEMA_NODES or depth > MAX_SCHEMA_DEPTH:
            raise SchemaError("JSON schema complexity limit exceeded")

        if isinstance(x, list):
            stack.extend((v, depth + 1) for v in x)
        elif isinstance(x, dict):
            stack.extend((v, depth + 1) for v in x.values())


def _refs(schema: object) -> Iterator[str]:
    stack = [schema]

    while stack:
        x = stack.pop()

        if isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, dict):
            ref = x.get("$ref")

            if isinstance(ref, str):
                yield ref

            stack.extend(x.values())


def _resolvable(schema: object) -> bool:
    resource = DRAFT7.create_resource(schema)
    registry = Registry().with_resource(resource.id() or "", resource).crawl()
    bases = ["", *(uri for uri in registry if uri)]

    for ref in _refs(schema):
        for base in bases:
            try:
                registry.resolver(base_uri=base).lookup(ref)
            except Unresolvable:
                continue
            break
        else:
            return False

    return True


def compile_local(schema: object) -> Draft7Validator:
    """Compile a bounded, self-contained Draft-07 schema that never fetches a reference."""
    if not isinstance(schema, bool | dict):
        raise SchemaError("JSON schema must be an object or a boolean")

    try:
        check_bounds(schema)
    except JsonError as err:
        raise SchemaError("JSON schema complexity limit exceeded") from err

    _complexity(schema)

    if isinstance(schema, dict):
        dialect = schema.get("$schema")

        if dialect is not None and not (isinstance(dialect, str) and dialect in DRAFT_07):
            raise SchemaError("JSON schema dialect is not Draft-07")

    try:
        Draft7Validator.check_schema(schema)
    except InvalidSchema as err:
        raise SchemaError("invalid JSON schema") from err

    if not _resolvable(schema):
        raise SchemaError("JSON schema reference does not resolve inside the schema")

    return Draft7Validator(schema, format_checker=FORMATS, registry=Registry())
