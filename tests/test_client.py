import asyncio
import json
import threading

import pytest
from conftest import (
    CONTEXT,
    INPUT,
    Flavor,
    discover,
    http_reply,
    open_client,
    params,
    run,
    scripted,
    serve,
)

import aclp


def context_app(**opts: object) -> aclp.ASGIApp:
    seen: list[str] = []

    def handle(p: aclp.events.InputSubmittedParams, ctx: aclp.CallContext) -> dict[str, list[str]]:
        return {"context": [f"blocks={len(p['content'])}", f"client={ctx.client}"]}

    return aclp.create_app(
        {
            "input.submitted": aclp.Callback(handle=handle, result=CONTEXT),
            "session.started": aclp.Callback(handle=lambda p, ctx: seen.append(p["sessionId"])),
        },
        **opts,  # type: ignore[arg-type]  # each test passes only valid create_app options
    )


def test_request_returns_the_validated_result(flavor: Flavor) -> None:
    async def scenario(url: str) -> dict[str, list[str]]:
        async with open_client(
            flavor, url, client={"name": "test", "version": "1.0", "harness": {"name": "pytest"}}
        ) as c:
            return await c.request("input.submitted", INPUT, CONTEXT)

    with serve(context_app()) as port:
        reply = run(scenario(f"http://127.0.0.1:{port}/aclp"))

    assert reply == {"context": ["blocks=1", "client=test/1.0 pytest"]}


def test_notifications_are_admitted_before_flush_returns(flavor: Flavor) -> None:
    got = threading.Event()

    app = aclp.create_app({"session.started": aclp.Callback(handle=lambda p, ctx: got.set())})

    async def scenario(url: str) -> None:
        async with open_client(flavor, url) as c:
            c.notify("session.started", params("session.started"))
            await c.flush()

    with serve(app) as port:
        run(scenario(f"http://localhost:{port}/aclp"))
        assert got.wait(5)


def test_flush_raises_every_delivery_failure_once(flavor: Flavor) -> None:
    failures: list[aclp.ClientError] = []

    async def scenario(url: str) -> None:
        async with open_client(flavor, url, on_error=failures.append) as c:
            c.notify("run.paused", {"sessionId": "s"})
            c.notify("run.resumed", {"sessionId": "s"})

            with pytest.raises(aclp.FlushError) as caught:
                await c.flush()

            assert [type(e) for e in caught.value.exceptions] == [aclp.StatusError] * 2
            assert all(
                isinstance(e, aclp.StatusError) and e.status == 400 for e in caught.value.exceptions
            )
            await c.flush()

    with serve(context_app()) as port:
        run(scenario(f"http://127.0.0.1:{port}/"))

    assert len(failures) == 2


def test_static_and_computed_authorization_reach_the_server(flavor: Flavor) -> None:
    app = aclp.create_app(
        {"input.submitted": aclp.Callback(handle=lambda p, ctx: {"context": []}, result=CONTEXT)},
        authorization="Bearer secret",
    )

    async def scenario(url: str) -> None:
        async with open_client(flavor, url, authorization="Bearer secret") as c:
            assert await c.request("input.submitted", INPUT, CONTEXT) == {"context": []}

        async with open_client(flavor, url, authorization=lambda: "Bearer secret") as c:
            assert await c.request("input.submitted", INPUT, CONTEXT) == {"context": []}

        async with open_client(flavor, url, authorization="Bearer wrong") as c:
            with pytest.raises(aclp.StatusError) as caught:
                await c.request("input.submitted", INPUT, CONTEXT)

            assert caught.value.status == 401

    with serve(app) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


def test_failing_authorization_provider_fails_the_call(flavor: Flavor) -> None:
    def provider() -> str:
        raise OSError("keychain locked")

    async def scenario() -> None:
        async with open_client(flavor, "http://127.0.0.1:9/aclp", authorization=provider) as c:
            with pytest.raises(aclp.AuthorizationError):
                await c.request("input.submitted", INPUT, CONTEXT)

    run(scenario())


def test_local_checks_fail_before_anything_is_sent(flavor: Flavor) -> None:
    async def scenario() -> None:
        async with open_client(flavor, "http://127.0.0.1:9/aclp", events=["input.submitted"]) as c:
            with pytest.raises(aclp.NotConsentedError):
                c.notify("session.started", params("session.started"))

            with pytest.raises(aclp.InvalidParamsError):
                await c.request("input.submitted", {"sessionId": "s", "content": []}, CONTEXT)

            with pytest.raises(aclp.InvalidParamsError):
                await c.request("input.submitted", {**INPUT, "extra": float("nan")}, CONTEXT)

    run(scenario())


def test_client_methods_are_always_consented(flavor: Flavor) -> None:
    got = threading.Event()

    app = aclp.create_app({"client.updated": aclp.Callback(handle=lambda p, ctx: got.set())})

    async def scenario(url: str) -> None:
        async with open_client(flavor, url, events=[]) as c:
            c.notify("client.updated", params("client.updated"))
            await c.flush()

    with serve(app) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))
        assert got.wait(5)


def test_callback_errors_surface_as_rpc_errors_without_their_text(flavor: Flavor) -> None:
    def fail(p: object, ctx: aclp.CallContext) -> object:
        raise ValueError("secret detail")

    app = aclp.create_app({"input.submitted": aclp.Callback(handle=fail, result=CONTEXT)})

    async def scenario(url: str) -> None:
        async with open_client(flavor, url) as c:
            with pytest.raises(aclp.RpcError) as caught:
                await c.request("input.submitted", INPUT, CONTEXT)

            assert caught.value.code == -32603
            assert caught.value.message == "Internal error"
            assert "Internal error" not in str(caught.value)

    with serve(app) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


def test_results_outside_the_installed_schema_are_rejected(flavor: Flavor) -> None:
    strict = aclp.ResultSchema[dict[str, list[str]]](
        {"type": "object", "required": ["context", "other"]}
    )

    async def scenario(url: str) -> None:
        async with open_client(flavor, url) as c:
            with pytest.raises(aclp.InvalidResultError):
                await c.request("input.submitted", INPUT, strict)

    with serve(context_app()) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


def test_a_server_that_never_answers_hits_the_deadline(flavor: Flavor) -> None:
    async def scenario(url: str) -> None:
        async with open_client(flavor, url, timeout=0.2) as c:
            with pytest.raises(aclp.DeadlineError):
                await c.request("input.submitted", INPUT, CONTEXT)

    with scripted(b"", delay=1) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (
            http_reply(
                200,
                b'{"jsonrpc":"2.0","id":"other","result":{"context":[]}}',
                "Content-Type: application/json",
            ),
            aclp.InvalidResponseError,
        ),
        (http_reply(200, b"{}", "Content-Type: text/plain"), aclp.InvalidResponseError),
        (
            http_reply(200, b"{not json", "Content-Type: application/json"),
            aclp.InvalidResponseError,
        ),
        (http_reply(500, b""), aclp.StatusError),
        (
            b"HTTP/1.1 200 OK\r\nContent-Length: 2000000\r\nContent-Type: application/json\r\n\r\n",
            aclp.InvalidResponseError,
        ),
        (b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: x\r\n\r\n", aclp.TransportError),
        (b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n{}", aclp.TransportError),
        (b"garbage\r\n\r\n", aclp.TransportError),
    ],
)
def test_malformed_replies_fail_the_request(
    flavor: Flavor, reply: bytes, error: type[aclp.ClientError]
) -> None:
    async def scenario(url: str) -> None:
        async with open_client(flavor, url) as c:
            with pytest.raises(error):
                await c.request("input.submitted", INPUT, CONTEXT)

    with scripted(reply) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


def test_chunked_replies_are_reassembled(flavor: Flavor) -> None:
    async def reply(req: bytes) -> bytes:
        id_ = json.loads(req.split(b"\r\n\r\n", 1)[1])["id"]
        body = json.dumps(
            {"jsonrpc": "2.0", "id": id_, "result": {"context": ["chunked"]}}
        ).encode()
        half = len(body) // 2
        chunks = b"".join(
            f"{len(p):x}\r\n".encode() + p + b"\r\n" for p in (body[:half], body[half:])
        )
        head = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: application/json\r\n\r\n"
        return head + chunks + b"0\r\n\r\n"

    async def scenario(url: str) -> None:
        async with open_client(flavor, url) as c:
            assert await c.request("input.submitted", INPUT, CONTEXT) == {"context": ["chunked"]}

    with scripted(reply) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


def test_async_notify_needs_the_open_context() -> None:
    client = aclp.AsyncClient("http://127.0.0.1:9/aclp")

    with pytest.raises(aclp.ClosedError):
        client.notify("session.started", params("session.started"))


def test_closed_clients_refuse_calls(flavor: Flavor) -> None:
    async def scenario() -> None:
        async with open_client(flavor, "http://127.0.0.1:9/aclp") as c:
            pass

        with pytest.raises(aclp.ClosedError):
            await c.request("input.submitted", INPUT, CONTEXT)

    run(scenario())


def test_async_capacity_is_bounded_at_64_outstanding_calls() -> None:
    async def scenario(url: str) -> None:
        async with aclp.AsyncClient(url, timeout=0.5) as c:
            for _ in range(64):
                c.notify("session.started", params("session.started"))

            with pytest.raises(aclp.CapacityError):
                c.notify("session.started", params("session.started"))

            with pytest.raises(aclp.FlushError):
                await c.flush()

    with scripted(b"", delay=1) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


def test_cancelling_an_async_request_propagates_and_frees_its_slot() -> None:
    async def scenario(url: str) -> None:
        async with aclp.AsyncClient(url, timeout=5) as c:
            task = asyncio.ensure_future(c.request("input.submitted", INPUT, CONTEXT))
            await asyncio.sleep(0.1)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            for _ in range(64):
                c.notify("session.started", params("session.started"))

    with scripted(http_reply(202, b""), delay=0.2) as port:
        run(scenario(f"http://127.0.0.1:{port}/aclp"))


def test_https_endpoints_trust_the_configured_ca(flavor: Flavor, tls: tuple[str, str, str]) -> None:
    ca, certfile, keyfile = tls

    async def scenario(url: str) -> None:
        async with open_client(flavor, url, ca=ca) as c:
            assert (await c.request("input.submitted", INPUT, CONTEXT))["context"][0] == "blocks=1"

        async with open_client(flavor, url) as c:
            with pytest.raises(aclp.TransportError):
                await c.request("input.submitted", INPUT, CONTEXT)

    with serve(context_app(), ssl_certfile=certfile, ssl_keyfile=keyfile) as port:
        run(scenario(f"https://localhost:{port}/aclp"))


@pytest.mark.parametrize(
    ("url", "opts"),
    [
        ("ftp://127.0.0.1/aclp", {}),
        ("http://user:pw@127.0.0.1/aclp", {}),
        ("http://127.0.0.1/aclp#x", {}),
        ("http://127.0.0.1:99999/aclp", {}),
        ("http://127.0.0.1/aclp", {"timeout": 0}),
        ("http://127.0.0.1/aclp", {"timeout": float("inf")}),
        ("http://127.0.0.1/aclp", {"authorization": "Bearer x\r\nHost: evil"}),
        ("http://127.0.0.1/aclp", {"client": {"name": ""}}),
        ("http://127.0.0.1/aclp", {"client": {"name": "café"}}),
        ("https://127.0.0.1/aclp", {"ca": "not a certificate"}),
    ],
)
def test_invalid_configuration_is_rejected_before_io(url: str, opts: dict[str, object]) -> None:
    with pytest.raises(aclp.ConfigError):
        aclp.Client(url, **opts)  # type: ignore[arg-type]  # deliberately invalid options

    with pytest.raises(aclp.ConfigError):
        aclp.AsyncClient(url, **opts)  # type: ignore[arg-type]  # deliberately invalid options


def test_failure_policy_defaults_to_fail_closed_guards_only(flavor: Flavor) -> None:
    async def scenario() -> None:
        async with open_client(flavor, "http://127.0.0.1:9/aclp") as c:
            assert c.failure_policy("tool.requested") == "deny"
            assert c.failure_policy("permission.requested") == "deny"
            assert c.failure_policy("input.submitted") == "allow"

        async with open_client(flavor, "http://127.0.0.1:9/aclp", failure_policy="allow") as c:
            assert c.failure_policy("tool.requested") == "allow"

    run(scenario())
    assert aclp.FAIL_CLOSED_METHODS == ("tool.requested", "permission.requested")


def test_discovery_reads_the_well_known_document(flavor: Flavor) -> None:
    app = aclp.create_app(
        {"input.submitted": aclp.Callback(handle=lambda p, ctx: {"context": []}, result=CONTEXT)},
        authorization="Bearer t",
        discovery=aclp.Discovery("https://aclp.example.com/events", name="Example"),
    )

    with serve(app) as port:
        doc = run(discover(flavor, f"http://127.0.0.1:{port}/anything?x=1"))

    assert doc == {
        "name": "Example",
        "endpoint": "https://aclp.example.com/events",
        "auth": {"methods": ["token"]},
        "events": ["input.submitted"],
        "requests": ["input.submitted"],
    }


def test_discovery_rejects_missing_or_invalid_documents(flavor: Flavor) -> None:
    with serve(context_app()) as port, pytest.raises(aclp.StatusError):
        run(discover(flavor, f"http://127.0.0.1:{port}"))

    bad = http_reply(
        200,
        b'{"endpoint":"ftp://x","auth":{"methods":[]},"events":[],"requests":[]}',
        "Content-Type: application/json",
    )

    with scripted(bad) as port, pytest.raises(aclp.DiscoveryError):
        run(discover(flavor, f"http://127.0.0.1:{port}"))
