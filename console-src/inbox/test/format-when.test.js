import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createInboxOrgan } from "../js/inbox.js";
import { formatWhen } from "../js/util.js";

const here = dirname(fileURLToPath(import.meta.url));
const NOW = Date.parse("2026-09-04T22:34:00Z");
const ADA_UPDATED = "2026-08-28T15:10:00Z";
const ADA_MESSAGE = "2026-08-28T14:02:00Z";

test("formatWhen absolute keeps day month time", () => {
  const stamp = formatWhen(ADA_UPDATED);
  assert.match(stamp, /28 Aug/);
  assert.match(stamp, /\d{1,2}:\d{2}/);
});

test("formatWhen relative covers now minutes hours yesterday and days", () => {
  const now = new Date(2026, 8, 4, 22, 34, 0);
  const rel = (date) => formatWhen(date.toISOString(), { relative: true, now });
  assert.equal(rel(new Date(2026, 8, 4, 22, 33, 30)), "now");
  assert.equal(rel(new Date(2026, 8, 4, 22, 20, 0)), "14m");
  assert.equal(rel(new Date(2026, 8, 4, 20, 34, 0)), "2h");
  assert.equal(rel(new Date(2026, 8, 3, 18, 0, 0)), "Yesterday");
  assert.equal(formatWhen(ADA_UPDATED, { relative: true, now: NOW }), "7d");
  const older = new Date("2026-08-01T12:00:00Z");
  assert.equal(
    formatWhen(older.toISOString(), { relative: true, now: NOW }),
    older.toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
  );
  assert.equal(formatWhen(""), "");
  assert.equal(formatWhen("not-a-date", { relative: true, now: NOW }), "");
});

test("list rows use relative time; thread keeps absolute", async () => {
  const snap = await createInboxOrgan({ viewId: "mine" }).ready();
  const row = snap.html.match(/data-ticket="t-ada-track"[\s\S]*?<\/button>/)?.[0] || "";
  const time = row.match(/<time class="ticket-time"([^>]*)>([^<]*)<\/time>/);
  assert.ok(time, "Ada list row has a time");
  const expectedRel = formatWhen(ADA_UPDATED, { relative: true });
  const expectedAbs = formatWhen(ADA_UPDATED);
  assert.equal(time[2], expectedRel);
  assert.doesNotMatch(time[2], /28 Aug,\s*\d{1,2}:\d{2}/);
  assert.match(time[1], new RegExp(`datetime="${ADA_UPDATED}"`));
  assert.match(time[1], new RegExp(`title="${expectedAbs.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"`));

  const bubble = snap.html.match(/<article class="bubble[\s\S]*?<time>([^<]*)<\/time>/);
  assert.ok(bubble, "thread message has a time");
  assert.equal(bubble[1], formatWhen(ADA_MESSAGE));
  assert.match(bubble[1], /28 Aug/);
  assert.match(bubble[1], /\d{1,2}:\d{2}/);
});

test("list source uses the one formatter in relative mode", () => {
  const list = readFileSync(join(here, "../js/tissues/list.js"), "utf8");
  const thread = readFileSync(join(here, "../js/tissues/thread.js"), "utf8");
  assert.match(list, /formatWhen\(ticket\.updatedAt,\s*\{\s*relative:\s*true\s*\}\)/);
  assert.match(list, /title="\$\{esc\(formatWhen\(ticket\.updatedAt\)\)\}"/);
  assert.match(thread, /formatWhen\(message\.at\)/);
  assert.doesNotMatch(thread, /relative:\s*true/);
});
