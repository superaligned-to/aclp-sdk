# aclp for Python

[ACLP](https://github.com/superaligned-to/aclp) sync and async clients and an ASGI callback server. Python 3.11+.

```sh
uv add superaligned-aclp
uv add uvicorn
```

## Example

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

```text
{'context': ['Prefer plain functions over classes.']}
```

```python
with aclp.Client("http://127.0.0.1:8787/aclp") as client:
    client.notify("session.started", {"sessionId": "session-1"})
    client.flush()

doc = aclp.discover("https://aclp.example.com")
policy = aclp.on_error_for("tool.requested")
```

## Development

```sh
uv run python scripts/check.py
```

MIT
