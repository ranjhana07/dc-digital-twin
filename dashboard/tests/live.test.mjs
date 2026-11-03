import assert from "node:assert/strict";
import test from "node:test";

import { backoffDelay } from "../js/live.js";

test("backoff grows and is capped", () => {
  const fixed = () => 0;
  assert.equal(backoffDelay(0, fixed), 250);
  assert.equal(backoffDelay(1, fixed), 500);
  assert.equal(backoffDelay(3, fixed), 2000);
  assert.equal(backoffDelay(20, fixed), 7500);
});

test("jitter stays inside the window", () => {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const low = backoffDelay(attempt, () => 0);
    const high = backoffDelay(attempt, () => 0.999);
    assert.ok(high >= low && high <= 15000);
  }
});
