import base64
import binascii
import contextlib
import copy
import doctest
import importlib

import pytest
from conftest import EXAMPLES, params
from hypothesis import given
from hypothesis import strategies as st

import aclp
from aclp.events import JsonValue

JSON = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(), inner, max_size=4),
    max_leaves=20,
)


@given(JSON)
def test_json_round_trips(val: object) -> None:
    assert aclp.decode_json(aclp.encode_json(val)) == val


@given(st.binary(max_size=64))
def test_decode_never_raises_anything_but_json_error(raw: bytes) -> None:
    with contextlib.suppress(aclp.JsonError):
        aclp.decode_json(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a": 1, "a": 2}',
        b"NaN",
        b"[Infinity]",
        b"1e400",
        b"\xef\xbb\xbf{}",
        b"\xff",
        b'"\\ud800"',
        b"[" * 66 + b"]" * 66,
        b"{} {}",
        b" " * (aclp.MAX_BODY_BYTES + 1),
    ],
)
def test_decode_rejects_json_outside_the_protocol_bounds(raw: bytes) -> None:
    with pytest.raises(aclp.JsonError):
        aclp.decode_json(raw)


@pytest.mark.parametrize("val", [float("nan"), {1: "x"}, object(), "\ud800", [[]] * 100_001])
def test_encode_rejects_values_that_are_not_bounded_json(val: object) -> None:
    with pytest.raises(aclp.JsonError):
        aclp.encode_json(val)


@pytest.mark.parametrize(("method", "p"), EXAMPLES)
def test_every_standard_event_example_validates(method: str, p: dict[str, object]) -> None:
    assert aclp.is_event_method(method)
    assert aclp.validate_params(method, p)


def image(data: str) -> dict[str, object]:
    return {"sessionId": "s", "content": [{"type": "image", "data": data, "mimeType": "image/png"}]}


@given(
    st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=-_ ", max_size=16
    )
)
def test_binary_content_must_be_canonical_base64(data: str) -> None:
    try:
        oracle = base64.b64encode(base64.b64decode(data, validate=True)).decode() == data
    except binascii.Error:
        oracle = False

    assert aclp.validate_params("input.submitted", image(data)) == oracle


@given(st.binary(max_size=48))
def test_encoded_bytes_are_accepted(raw: bytes) -> None:
    assert aclp.validate_params("input.submitted", image(base64.b64encode(raw).decode()))


def network(origin: str) -> dict[str, object]:
    p = copy.deepcopy(params("permission.requested"))
    p["operation"] = {"kind": "network", "origin": origin}
    return p


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "https://example.com/",
        "http://example.com:8080/",
        "HTTPS://Example.com",
        "http://[::1]:80",
        "http://127.0.0.1",
    ],
)
def test_network_origins_with_scheme_host_and_port_are_accepted(origin: str) -> None:
    assert aclp.validate_params("permission.requested", network(origin))


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com/a/..",
        "https://example.com/%2e",
        "https:example.com",
        "https://@example.com",
        "https://user@example.com",
        "https://example.com/?",
        "https://example.com/#",
        "https://example.com:99999",
        "https://example.com:",
        "https://exa mple.com",
        "ftp://example.com",
        "https://",
        "http://[::1",
    ],
)
def test_network_origins_with_anything_else_are_rejected(origin: str) -> None:
    assert not aclp.validate_params("permission.requested", network(origin))


@given(st.text(max_size=40))
def test_origin_and_uri_checks_never_raise(text: str) -> None:
    aclp.validate_params("permission.requested", network(text))
    aclp.validate_params("permission.requested", network(f"https://{text}"))
    aclp.validate_params("resource.changed", {"resource": {"uri": text}, "change": "created"})


def test_list_identities_must_be_unique() -> None:
    perm = copy.deepcopy(params("permission.requested"))
    perm["options"] = [
        {"id": "a", "label": "Allow", "decision": "allow"},
        {"id": "a", "label": "Deny", "decision": "deny"},
    ]
    plan = {
        "sessionId": "s",
        "steps": [
            {"id": "1", "title": "x", "status": "pending"},
            {"id": "1", "title": "y", "status": "pending"},
        ],
    }
    config = {"changes": [{"key": "k", "value": 1}, {"key": "k", "value": 2}]}
    item = {"call": {"id": "c", "name": "t"}, "outcome": {"status": "succeeded"}}
    batch = {"sessionId": "s", "calls": [item, copy.deepcopy(item)]}

    assert not aclp.validate_params("permission.requested", perm)
    assert not aclp.validate_params("plan.updated", plan)
    assert not aclp.validate_params("configuration.changed", config)
    assert not aclp.validate_params("tool.batch.finished", batch)


def test_embedded_schemas_must_be_local_draft_07() -> None:
    def catalog(schema: object) -> dict[str, object]:
        return {"catalog": "tools", "entries": [{"name": "t", "inputSchema": schema}]}

    assert aclp.validate_params("catalog.changed", catalog({"type": "object"}))
    assert not aclp.validate_params(
        "catalog.changed", catalog({"$ref": "https://example.invalid/s"})
    )
    assert not aclp.validate_params(
        "catalog.changed", catalog({"$schema": "https://json-schema.org/draft/2020-12/schema"})
    )
    assert not aclp.validate_params("catalog.changed", catalog({"type": "nonsense"}))


def test_accepted_form_answers_must_satisfy_the_form_schema() -> None:
    def resolved(val: object) -> dict[str, object]:
        return {
            "sessionId": "s",
            "interaction": {"kind": "form", "message": "Age?", "schema": {"type": "integer"}},
            "response": {"status": "accepted", "value": val},
        }

    assert aclp.validate_params("interaction.resolved", resolved(3))
    assert not aclp.validate_params("interaction.resolved", resolved("three"))


def test_result_schemas_are_bounded_local_draft_07() -> None:
    local = aclp.ResultSchema[int](
        {"definitions": {"n": {"type": "integer"}}, "$ref": "#/definitions/n"}
    )

    assert local.validate(1)
    assert not local.validate("1")

    for bad in [
        {"$ref": "https://example.invalid/missing"},
        {"$ref": "#/definitions/missing"},
        {"$schema": "https://json-schema.org/draft/2020-12/schema"},
        {"enum": list(range(2_048))},
        {"type": 5},
    ]:
        with pytest.raises(aclp.SchemaError):
            aclp.ResultSchema[object](bad)  # type: ignore[arg-type]  # deliberately invalid schemas

    for dialect in [
        "http://json-schema.org/draft-07/schema#",
        "https://json-schema.org/draft-07/schema",
    ]:
        aclp.ResultSchema[object]({"$schema": dialect})


def test_result_schema_keeps_its_own_copy() -> None:
    schema: dict[str, JsonValue] = {"type": "string"}
    result = aclp.ResultSchema[str](schema)
    schema["type"] = "integer"

    assert result.validate("x")
    assert result.schema == {"type": "string"}


def test_on_error_for_defaults_only_tool_and_permission_guards_to_deny() -> None:
    assert [
        aclp.on_error_for(m)
        for m in ("tool.requested", "permission.requested", "input.submitted", "client.registered")
    ] == [
        "deny",
        "deny",
        "allow",
        "allow",
    ]
    assert aclp.on_error_for("tool.requested", "allow") == "allow"


def test_error_strings_never_echo_server_text() -> None:
    err = aclp.RpcError(-32000, "token=abc")

    assert "abc" not in str(err)
    assert err.message == "token=abc"
    assert isinstance(err, aclp.ClientError)
    assert isinstance(aclp.FlushError([err]), aclp.AclpError)


@pytest.mark.parametrize(
    "module",
    ["aclp._json", "aclp._uri", "aclp._semantics", "aclp._validation", "aclp._on_error", "aclp"],
)
def test_docstring_examples_run(module: str) -> None:
    res = doctest.testmod(importlib.import_module(module))

    assert res.attempted > 0
    assert res.failed == 0
