import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { greeting } from "../dist/app.js";

test("greeting returns the starter message", () => {
  assert.equal(greeting(), "Hello from project-typescript-starter!");
});

test("the built example runs", () => {
  const main = fileURLToPath(new URL("../dist/main.js", import.meta.url));
  const result = spawnSync(process.execPath, [main], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, "Hello from project-typescript-starter!\n");
});
