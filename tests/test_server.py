import asyncio
import json
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import cast

import pytest
from conftest import CONTEXT, INPUT, params, run

import aclp


@dataclass
class Reply:
    status: int
    headers: dict[str, str]
    body: bytes

    def rpc(self) -> dict[str, object]:
        assert self.headers["content-type"] == "application/json"
        val = json.loads(self.body)
        assert isinstance(val, dict)
        return val


@dataclass
class Call:
    method: str = "POST"
    path: str = "/aclp"
    headers: list[tuple[str, str]] = field(
        default_factory=lambda: [("host", "127.0.0.1:8787"), ("content-type", "application/json")]
    )
    body: bytes = b""
    peer: str = "127.0.0.1"
    local: tuple[str, int] = ("127.0.0.1", 8787)


async def call(app: aclp.ASGIApp, c: Call) -> Reply:
    scope = {
        "type": "http",
        "method": c.method,
        "path": c.path,
        "raw_path": c.path.encode(),
        "headers": [(k.encode(), v.encode()) for k, v in c.headers],
        "client": (c.peer, 50000),
        "server": c.local,
    }
    sent: list[MutableMapping[str, object]] = []
    chunks = [{"type": "http.request", "body": c.body, "more_body": False}]

    async def receive() -> MutableMapping[str, object]:
        if chunks:
            return chunks.pop()
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    async def send(msg: MutableMapping[str, object]) -> None:
        sent.append(msg)

    await app(scope, receive, send)
    start = sent[0]
    pairs = cast("list[tuple[bytes, bytes]]", start["headers"])
    body = b"".join(cast("bytes", m.get("body", b"")) for m in sent[1:])
    return Reply(cast("int", start["status"]), {k.decode(): v.decode() for k, v in pairs}, body)


def message(method: str, p: object, id_: str | None = "r1") -> bytes:
    msg: dict[str, object] = {"jsonrpc": "2.0", "method": method, "params": p}

    if id_ is not None:
        msg["id"] = id_

    return json.dumps(msg).encode()


def make_app(**opts: object) -> tuple[aclp.ASGIApp, list[aclp.CallbackError], list[str]]:
    errors: list[aclp.CallbackError] = []
    seen: list[str] = []

    def fail(p: object, ctx: aclp.CallContext) -> object:
        raise RuntimeError("boom")

    async def notice(p: aclp.events.SessionStartedParams, ctx: aclp.CallContext) -> None:
        seen.append(p["sessionId"])

    app = aclp.create_app(
        {
            "input.submitted": aclp.Callback(
                handle=lambda p, ctx: {"context": ["x"]}, result=CONTEXT
            ),
            "tool.requested": aclp.Callback(handle=fail, result=CONTEXT),
            "model.requested": aclp.Callback(handle=lambda p, ctx: {"context": 1}, result=CONTEXT),
            "session.started": aclp.Callback(handle=notice),
            "session.ended": aclp.Callback(handle=fail),
        },
        on_error=errors.append,
        **opts,  # type: ignore[arg-type]  # each test passes only valid create_app options
    )
    return app, errors, seen


def test_requests_get_their_validated_result() -> None:
    app, _, _ = make_app()
    reply = run(call(app, Call(body=message("input.submitted", INPUT))))

    assert reply.status == 200
    assert reply.rpc() == {"jsonrpc": "2.0", "id": "r1", "result": {"context": ["x"]}}


def test_notifications_are_admitted_with_an_empty_202_and_then_run() -> None:
    app, _, seen = make_app()
    reply = run(call(app, Call(body=message("session.started", params("session.started"), None))))

    assert (reply.status, reply.body) == (202, b"")
    assert seen == ["session-1"]


def test_every_standard_event_example_is_admitted() -> None:
    from conftest import EXAMPLES

    app = aclp.create_app({m: aclp.Callback(handle=lambda p, ctx: None) for m, _ in EXAMPLES})

    for m, p in EXAMPLES:
        assert run(call(app, Call(body=message(m, p, None)))).status == 202, m


@pytest.mark.parametrize(
    ("body", "status", "code", "id_"),
    [
        (b"{nope", 400, -32700, None),
        (b'[{"jsonrpc":"2.0","id":"a","method":"input.submitted","params":{}}]', 400, -32600, None),
        (
            b'{"jsonrpc":"2.0","id":"a","method":"input.submitted","params":{},"x":1}',
            400,
            -32600,
            "a",
        ),
        (b'{"jsonrpc":"2.0","id":1,"method":"input.submitted","params":{}}', 400, -32600, None),
        (
            b'{"jsonrpc":"2.0","id":"a","id":"b","method":"input.submitted","params":{}}',
            400,
            -32700,
            None,
        ),
        (message("unknown.method", {}), 200, -32601, "r1"),
        (message("input.submitted", {"sessionId": "s"}), 200, -32602, "r1"),
        (message("session.started", {"sessionId": "s"}), 200, -32601, "r1"),
        (message("run.paused", {"sessionId": "s"}), 200, -32601, "r1"),
    ],
)
def test_invalid_requests_get_the_json_rpc_error_the_binding_requires(
    body: bytes, status: int, code: int, id_: str | None
) -> None:
    app, _, _ = make_app()
    reply = run(call(app, Call(body=body)))

    assert reply.status == status
    assert reply.rpc()["id"] == id_
    assert reply.rpc()["error"] == {"code": code, "message": reply.rpc()["error"]["message"]}  # type: ignore[index]


@pytest.mark.parametrize(
    "body",
    [
        message("unknown.method", {}, None),
        message("session.started", {}, None),
        message("run.paused", {"sessionId": "s"}, None),
        b'{"jsonrpc":"2.0","method":"session.started","params":{"sessionId":"s"},"x":1}',
    ],
)
def test_invalid_notifications_get_an_empty_400(body: bytes) -> None:
    app, _, _ = make_app()
    reply = run(call(app, Call(body=body)))

    assert (reply.status, reply.body) == (400, b"")


def test_callback_failures_answer_32603_and_reach_on_error() -> None:
    app, errors, _ = make_app()

    raised = run(call(app, Call(body=message("tool.requested", params("tool.requested")))))
    invalid = run(call(app, Call(body=message("model.requested", params("model.requested")))))
    notified = run(call(app, Call(body=message("session.ended", params("session.ended"), None))))

    assert raised.rpc()["error"] == {"code": -32603, "message": "Internal error"}
    assert invalid.rpc()["error"] == {"code": -32603, "message": "Internal error"}
    assert notified.status == 202
    assert [e.method for e in errors] == ["tool.requested", "model.requested", "session.ended"]
    assert isinstance(errors[0].__cause__, RuntimeError)
    assert "boom" not in str(errors[0])


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"peer": "10.0.0.2"}, 403),
        ({"local": ("10.0.0.1", 8787)}, 403),
        ({"headers": [("host", "127.0.0.1:9999"), ("content-type", "application/json")]}, 403),
        ({"headers": [("host", "example.com:8787"), ("content-type", "application/json")]}, 403),
        (
            {
                "headers": [
                    ("host", "127.0.0.1:8787"),
                    ("host", "127.0.0.1:8787"),
                    ("content-type", "application/json"),
                ]
            },
            403,
        ),
        (
            {
                "headers": [
                    ("host", "127.0.0.1:8787"),
                    ("origin", "http://evil"),
                    ("content-type", "application/json"),
                ]
            },
            403,
        ),
        ({"headers": [("host", "127.0.0.1:08787"), ("content-type", "application/json")]}, 403),
        ({"path": "//aclp"}, 403),
        ({"method": "PUT"}, 405),
        ({"headers": [("host", "127.0.0.1:8787"), ("content-type", "text/plain")]}, 415),
        (
            {
                "headers": [
                    ("host", "127.0.0.1:8787"),
                    ("content-type", "application/json"),
                    ("content-length", "2000000"),
                ]
            },
            413,
        ),
        ({"body": b" " * (aclp.MAX_BODY_BYTES + 1)}, 413),
    ],
)
def test_http_admission_failures_get_an_empty_status(
    change: dict[str, object], status: int
) -> None:
    app, _, _ = make_app()
    c = Call(body=message("input.submitted", INPUT))

    for k, v in change.items():
        setattr(c, k, v)

    reply = run(call(app, c))

    assert (reply.status, reply.body) == (status, b"")
    assert reply.headers["connection"] == "close"

    if status == 405:
        assert reply.headers["allow"] == "POST"


def test_loopback_names_and_mapped_addresses_are_accepted() -> None:
    app, _, _ = make_app()

    for host, peer in [
        ("localhost:8787", "::ffff:127.0.0.1"),
        ("[::1]:8787", "::1"),
        ("LOCALHOST:8787", "127.0.0.1"),
    ]:
        c = Call(
            headers=[("host", host), ("content-type", "application/json; charset=utf-8")],
            peer=peer,
            body=message("input.submitted", INPUT),
        )
        assert run(call(app, c)).status == 200, host


def test_authorization_is_required_and_challenged() -> None:
    app, _, _ = make_app(authorization="Bearer secret")
    base = [("host", "127.0.0.1:8787"), ("content-type", "application/json")]

    missing = run(call(app, Call(body=message("input.submitted", INPUT))))
    wrong = run(
        call(
            app,
            Call(
                headers=[*base, ("authorization", "Bearer nope")],
                body=message("input.submitted", INPUT),
            ),
        )
    )
    twice = run(
        call(
            app,
            Call(
                headers=[
                    *base,
                    ("authorization", "Bearer secret"),
                    ("authorization", "Bearer secret"),
                ],
                body=message("input.submitted", INPUT),
            ),
        )
    )
    right = run(
        call(
            app,
            Call(
                headers=[*base, ("authorization", "Bearer secret")],
                body=message("input.submitted", INPUT),
            ),
        )
    )

    assert [missing.status, wrong.status, twice.status, right.status] == [401, 401, 401, 200]
    assert missing.headers["www-authenticate"] == 'Bearer realm="aclp"'


def test_public_hosts_accept_any_peer_with_authorization() -> None:
    app, _, _ = make_app(authorization="Bearer secret", hosts=["ACLP.example.com"])
    headers = [
        ("host", "aclp.example.com"),
        ("content-type", "application/json"),
        ("authorization", "Bearer secret"),
    ]
    reply = run(
        call(
            app,
            Call(
                headers=headers,
                peer="203.0.113.9",
                local=("10.0.0.1", 443),
                body=message("input.submitted", INPUT),
            ),
        )
    )

    assert reply.status == 200


def test_callbacks_beyond_32_get_429_until_a_slot_frees() -> None:
    release = asyncio.Event()

    async def hold(p: object, ctx: aclp.CallContext) -> None:
        await release.wait()

    app = aclp.create_app({"session.started": aclp.Callback(handle=hold)})

    async def scenario() -> list[int]:
        body = message("session.started", params("session.started"), None)
        held = [asyncio.ensure_future(call(app, Call(body=body))) for _ in range(32)]
        await asyncio.sleep(0.05)
        over = await call(app, Call(body=body))
        release.set()
        statuses = [r.status for r in await asyncio.gather(*held)]
        after = await call(app, Call(body=body))
        return [over.status, *set(statuses), after.status]

    assert run(scenario()) == [429, 202, 202]


def test_discovery_is_served_without_credentials() -> None:
    app, _, _ = make_app(
        authorization="Bearer secret", discovery=aclp.Discovery("https://aclp.example.com/aclp")
    )
    reply = run(call(app, Call(method="GET", path="/.well-known/aclp")))

    assert reply.status == 200
    assert reply.rpc() == {
        "endpoint": "https://aclp.example.com/aclp",
        "auth": {"methods": ["token"]},
        "events": [
            "input.submitted",
            "model.requested",
            "session.ended",
            "session.started",
            "tool.requested",
        ],
        "requests": ["input.submitted", "model.requested", "tool.requested"],
    }


def test_discovery_is_404_when_not_configured() -> None:
    app, _, _ = make_app()

    assert run(call(app, Call(method="GET", path="/.well-known/aclp"))).status == 404


def test_lifespan_completes_startup_and_shutdown() -> None:
    app, _, _ = make_app()
    inbox: list[MutableMapping[str, object]] = [
        {"type": "lifespan.shutdown"},
        {"type": "lifespan.startup"},
    ]
    sent: list[MutableMapping[str, object]] = []

    async def receive() -> MutableMapping[str, object]:
        return inbox.pop()

    async def send(msg: MutableMapping[str, object]) -> None:
        sent.append(msg)

    async def scenario() -> None:
        await app({"type": "lifespan"}, receive, send)

    run(scenario())

    assert [m["type"] for m in sent] == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


@pytest.mark.parametrize(
    "opts",
    [
        {"authorization": "token-without-scheme"},
        {"authorization": "Bearer x\r\nHost: evil"},
        {"hosts": ["aclp.example.com"]},
        {"hosts": ["aclp.example.com:443"], "authorization": "Bearer x"},
        {"discovery": aclp.Discovery("ftp://aclp.example.com")},
    ],
)
def test_invalid_server_configuration_is_rejected(opts: dict[str, object]) -> None:
    with pytest.raises(aclp.ConfigError):
        aclp.create_app({}, **opts)  # type: ignore[arg-type]  # deliberately invalid options


def test_unknown_callback_methods_are_rejected() -> None:
    with pytest.raises(aclp.ConfigError):
        aclp.create_app({"not.a.method": aclp.Callback(handle=lambda p, ctx: None)})
