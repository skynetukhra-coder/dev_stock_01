import test from "node:test";
import assert from "node:assert/strict";
import { appStatus } from "../src/index.mjs";

test("mobile bootstrap is loadable", () => {
  assert.equal(appStatus, "bootstrap");
});
