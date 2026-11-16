# Repository rules

- Keep one package, `superaligned-aclp`, importing as `aclp`, with a `src/` layout. The public surface is `aclp.__all__` plus `aclp.events`; everything else lives in underscore modules. Protocol definitions belong in `superaligned-to/aclp`.
- Generate `src/aclp/events.py` and `src/aclp/_methods.py` with `uv run python scripts/generate.py`; do not edit them by hand. Update `protocol-source.json` and `src/aclp/schema.json` together.
- Write client and HTTP code in `_async_client.py` and `_async_http.py`; `uv run python scripts/unasync.py` generates the sync twins. Only `_async_io.py` and `_sync_io.py` differ by hand.
- Keep behavior at parity with the TypeScript and Rust SDKs; reuse `tests/event-examples.json` rather than copying expectations by hand.
- Keep callbacks application-neutral. Authentication uses configured HTTP credentials; OAuth and harness adapters are outside this SDK.
- The library never retries, logs, reads environment variables or starts unowned tasks. Runtime dependencies are `jsonschema` and `referencing` only; record the reason next to any new one.
- Run `uv run python scripts/check.py` before committing. Test through the public API, and run each behavior test against both clients.
- Use one-line conventional commits. Preserve blank lines between logical blocks.
