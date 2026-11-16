import copy
from typing import Generic, TypeGuard, TypeVar

from aclp._errors import JsonError
from aclp._json import check_bounds
from aclp._schema import compile_local
from aclp.events import JsonSchema

T_co = TypeVar("T_co", covariant=True)


class ResultSchema(Generic[T_co]):
    """The installed result schema for a request method, and the type its results take.

    The schema is a bounded, self-contained Draft-07 schema; it is copied on construction.
    Parametrize the class with the type the schema describes. The type is not checked
    against the schema, so keep the two in agreement.

    >>> context = ResultSchema[dict[str, list[str]]]({
    ...     "type": "object",
    ...     "properties": {"context": {"type": "array", "items": {"type": "string"}}},
    ...     "required": ["context"],
    ... })
    >>> context.validate({"context": ["Prefer pure functions."]})
    True
    >>> context.validate({"context": "x"})
    False

    Raises `SchemaError` for a schema over 2,048 nodes or 32 levels, another dialect, an
    invalid schema, or a `$ref` outside the document. Instances are immutable and thread-safe.
    """

    __module__ = "aclp"

    __slots__ = ("_schema", "_validator")

    def __init__(self, schema: JsonSchema) -> None:
        self._schema = copy.deepcopy(schema)
        self._validator = compile_local(self._schema)

    @property
    def schema(self) -> JsonSchema:
        """A copy of the installed schema."""
        return copy.deepcopy(self._schema)

    def validate(self, val: object) -> TypeGuard[T_co]:
        """Whether `val` is bounded JSON that satisfies the schema."""
        try:
            check_bounds(val)
        except (JsonError, UnicodeError):
            return False

        return bool(self._validator.is_valid(val))
