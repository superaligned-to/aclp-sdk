import assert from "node:assert/strict";
import { test } from "node:test";
import { createServer, defineResult } from "../index.ts";
import { addServer, findServer } from "./registry.ts";
import { setEvents } from "./servers.ts";
import { listen, tempEnv } from "./test-support.ts";

const context = defineResult<{ context: string[] }>({
  type: "object",
  properties: { context: { type: "array", items: { type: "string" } } },
  required: ["context"],
});

test("re-enabling an event restores it as a request the server answers", async (t) => {
  const env = tempEnv(t);

  const url = await listen(
    t,
    createServer(
      {
        "client.updated": { handle: () => undefined },
        "input.submitted": { result: context, handle: () => ({ context: [] }) },
        "tool.finished": { handle: () => undefined },
      },
      { discovery: { endpoint: "http://127.0.0.1/aclp" } },
    ),
  );

  addServer(env, {
    name: "memory",
    endpoint: `${url}/aclp`,
    harnesses: "all",
    events: ["input.submitted", "tool.finished"],
    requests: ["input.submitted"],
    auth: { type: "none" },
  });

  await setEvents(env, "memory", ["tool.finished"]);
  assert.deepEqual(findServer(env, "memory").requests, []);

  await setEvents(env, "memory", ["input.submitted", "tool.finished"]);
  assert.deepEqual(findServer(env, "memory").requests, ["input.submitted"]);
});
