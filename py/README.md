# aclp for Python

Python client and callback server for the [Agent Context Lifecycle Protocol](https://github.com/superaligned-to/aclp). The client sends typed lifecycle events to local or remote servers over HTTP or HTTPS, with a sync `Client` and an `AsyncClient` that share one API. The server is an ASGI application that validates each event, runs your callback and checks its result against a JSON Schema.

Requires Python 3.11 or later.

```sh
pip install superaligned-aclp
```

## Example

The example serves the app with [uvicorn](https://www.uvicorn.org/), which is not a dependency of this package: `pip install uvicorn`.

```python
import asyncio

import uvicorn

import aclp
from aclp.events import InputSubmittedParams

context = aclp.ResultSchema[dict[str, list[str]]](
    {
        "type": "object",
        "properties": {"context": {"type": "array", "items": {"type": "string"}}},
        "required": ["context"],
        "additionalProperties": False,
    }
)


def advise(params: InputSubmittedParams, ctx: aclp.CallContext) -> dict[str, list[str]]:
    text = " ".join(b["text"] for b in params["content"] if b["type"] == "text")
    return {"context": ["Prefer plain functions over classes."] if "class" in text else []}


app = aclp.create_app({"input.submitted": aclp.Callback(handle=advise, result=context)})


async def main() -> None:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8787, log_level="warning"))

    async with asyncio.TaskGroup() as tg:
        tg.create_task(server.serve())

        while not server.started:
            await asyncio.sleep(0.01)

        async with aclp.AsyncClient("http://127.0.0.1:8787/aclp") as client:
            reply = await client.request(
                "input.submitted",
                {
                    "sessionId": "session-1",
                    "content": [{"type": "text", "text": "Create a class."}],
                },
                context,
            )

        print(reply)
        server.should_exit = True


asyncio.run(main())
```

It prints `{'context': ['Prefer plain functions over classes.']}`.

Notifications use `client.notify(method, params)` and `await client.flush()`; inside `async with`, the `AsyncClient` delivers them in the background, and the sync `Client` delivers each one before `notify` returns. A failed request raises a `ClientError`; `client.failure_policy(method)` says whether the harness should deny or allow the action the request guards. `aclp.discover(url)` reads a server's `/.well-known/aclp` document.

The server is loopback-only unless you name public hosts, which require `authorization`. Run it under an ASGI server with a bounded connection count.

## Development

```sh
uv run python scripts/check.py
```

Licensed under [MIT](LICENSE).
