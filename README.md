# ACLP SDKs

Client and callback-server libraries for the [Agent Context Lifecycle Protocol](https://github.com/superaligned-to/aclp), one directory per language. Each SDK sends typed lifecycle events over HTTP and serves callbacks that validate params and results against the same pinned schema.

| Directory | Package | Install |
| --- | --- | --- |
| [`ts`](ts) | [`@superaligned/aclp`](https://www.npmjs.com/package/@superaligned/aclp), also the `aclp` CLI for agent harnesses | `pnpm add @superaligned/aclp` |
| [`rs`](rs) | [`aclp`](https://crates.io/crates/aclp) | `cargo add aclp` |
| [`py`](py) | [`superaligned-aclp`](https://pypi.org/project/superaligned-aclp/) | `uv add superaligned-aclp` |

Each directory's README has a complete example. The protocol itself, its events and its schema live in [superaligned-to/aclp](https://github.com/superaligned-to/aclp).

Licensed under [MIT](LICENSE).
