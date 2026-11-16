# aclp for TypeScript

[ACLP](https://github.com/superaligned-to/aclp) client, callback server and the `aclp` harness CLI.

## CLI

```sh
npx @superaligned/aclp install claude-code
npx @superaligned/aclp server add memory --url http://127.0.0.1:8788/aclp
npx @superaligned/aclp server events memory --on-error deny
npx @superaligned/aclp status
npx @superaligned/aclp help
```

| Support | Harnesses |
| --- | --- |
| Context before the model | Claude Code, Codex, OpenCode, Pi, OMP, Hermes Agent, Gemini CLI, Qwen Code, Factory Droid, Devin CLI, GitHub Copilot CLI, Kiro CLI, Amp, Cline CLI/SDK, OpenClaw |
| Observe only | Cursor, Windsurf, Auggie CLI, Goose, Crush |
| MCP tool | Claude Desktop, ChatGPT Desktop, Zed |

Failed `tool.requested` and `permission.requested` requests deny; other failures allow. Credentials go to the OS keychain or a 0600 file.

## SDK

```sh
pnpm add @superaligned/aclp
```

```ts
import { createClient, createServer, defineResult } from "@superaligned/aclp";

const context = defineResult<{ context: string[] }>({
  type: "object",
  properties: { context: { type: "array", items: { type: "string" } } },
  required: ["context"],
  additionalProperties: false,
});

const server = createServer({
  "input.submitted": {
    result: context,
    handle: () => ({ context: ["Prefer pure functions and immutable values."] }),
  },
});

await new Promise<void>((resolve) => server.listen(8787, "127.0.0.1", resolve));

const client = createClient({ url: "http://127.0.0.1:8787/events" });

const reply = await client.request("input.submitted", {
  sessionId: "session-1",
  content: [{ type: "text", text: "Create a TypeScript class." }],
}, context);

client.notify("tool.finished", {
  sessionId: "session-1",
  call: { id: "call-1", name: "bash" },
  outcome: { status: "succeeded" },
});

await client.flush();
```

Harness tooling: `@superaligned/aclp/hooks`.

## Development

```sh
pnpm install --frozen-lockfile
pnpm check
```

MIT
