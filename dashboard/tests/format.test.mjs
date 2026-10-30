import assert from "node:assert/strict";
import test from "node:test";

import { escapeHtml, formatValue, scoreColor, shortKey, titleCase } from "../js/format.js";

test("formats values per metric", () => {
  assert.equal(formatValue("inlet_temp", 23.456), "23.5");
  assert.equal(formatValue("fan_rpm", 4821.4), "4,821");
  assert.equal(formatValue("cpu_load", 0.537), "54%");
  assert.equal(formatValue("pre_fec_ber", 0.0000012), "1.2e-6");
  assert.equal(formatValue("inlet_temp", null), "-");
});

test("title casing and short keys", () => {
  assert.equal(titleCase("pre_fec_ber"), "Pre Fec Ber");
  assert.equal(shortKey("dc1/hall-a/r01/srv-01"), "r01/srv-01");
});

test("score colors follow the health bands", () => {
  assert.equal(scoreColor(90), "var(--ok)");
  assert.equal(scoreColor(70), "var(--warn)");
  assert.equal(scoreColor(10), "var(--crit)");
});

test("escapes markup", () => {
  assert.equal(escapeHtml('<b a="1">&</b>'), "&lt;b a=&quot;1&quot;&gt;&amp;&lt;/b&gt;");
});
