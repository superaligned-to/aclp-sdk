# ACLP SDKs

[ACLP](https://github.com/superaligned-to/aclp) clients and callback servers.

| Dir | Package | Install |
| --- | --- | --- |
| [`ts`](ts) | `@superaligned/aclp` | `pnpm add @superaligned/aclp` |
| [`rs`](rs) | `aclp` | `cargo add aclp` |
| [`py`](py) | `superaligned-aclp` | `uv add superaligned-aclp` |

## TypeScript

```ts
import { createClient, defineResult } from "@superaligned/aclp";

const context = defineResult<{ context: string[] }>({
  type: "object",
  properties: { context: { type: "array", items: { type: "string" } } },
  required: ["context"],
});

const client = createClient({ url: "http://127.0.0.1:8787/aclp" });

const reply = await client.request("input.submitted", {
  sessionId: "session-1",
  content: [{ type: "text", text: "Create a class." }],
}, context);
```

```sh
npx @superaligned/aclp install claude-code
npx @superaligned/aclp server add memory --url http://127.0.0.1:8787/aclp
```

## Rust

```rust
use aclp::events::{ContentBlock, InputSubmittedParams};
use aclp::{Client, ClientOptions, ResultSchema};
use serde_json::{Value, json};

let context = ResultSchema::<Value>::new(json!({ "type": "object" }))?;

let client = Client::new(ClientOptions::new("http://127.0.0.1:8787/aclp"))?;

let input = InputSubmittedParams {
    session_id: "session-1".to_owned(),
    run_id: None,
    agent_id: None,
    content: vec![ContentBlock::Text { text: "Create a class.".to_owned() }],
    structured_content: None,
};

let reply = client.request(&input, &context).await?;
```

## Python

```python
import aclp

context = aclp.ResultSchema[dict[str, list[str]]]({"type": "object"})

with aclp.Client("http://127.0.0.1:8787/aclp") as client:
    reply = client.request(
        "input.submitted",
        {"sessionId": "session-1", "content": [{"type": "text", "text": "Create a class."}]},
        context,
    )
```

## Development

```sh
(cd ts && pnpm install --frozen-lockfile && pnpm check)
(cd rs && cargo xtask check && cargo xtask interop ../ts)
(cd py && uv run python scripts/check.py)
```

MIT
