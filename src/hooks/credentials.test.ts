import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { securityLine } from "./credentials.ts";

test("a keychain command line rejects a line break", () => {
  assert.throws(() => securityLine(["-w", "a\nb"]), /line break/);
});

test("a keychain secret round-trips through security -i unchanged", {
  skip: process.platform !== "darwin",
}, (t) => {
  const dir = mkdtempSync(join(tmpdir(), "aclp-keychain-"));

  const keychain = join(dir, "test.keychain-db");

  const secret = `{"accessToken":"a b\\"c\\\\d$e'f"}`;

  t.after(() => {
    execFileSync("security", ["delete-keychain", keychain]);
    rmSync(dir, { recursive: true, force: true });
  });

  execFileSync("security", ["create-keychain", "-p", "test", keychain]);

  execFileSync("security", ["-i"], {
    input: securityLine([
      "add-generic-password",
      "-s",
      "aclp",
      "-a",
      "memory",
      "-w",
      secret,
      keychain,
    ]),
  });

  const stored = execFileSync(
    "security",
    ["find-generic-password", "-s", "aclp", "-a", "memory", "-w", keychain],
    { encoding: "utf8" },
  ).trimEnd();

  assert.equal(stored, secret);
});
