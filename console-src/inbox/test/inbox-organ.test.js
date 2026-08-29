import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { IDS } from "../js/fixtures/cute-things.js";
import { createInboxOrgan } from "../js/inbox.js";
import { createFixtureShop } from "../js/shop/fixture-shop.js";

const here = dirname(fileURLToPath(import.meta.url));

function sourceTree() {
  const files = [
    "../index.html",
    "../styles.css",
    "../js/boot.js",
    "../js/inbox.js",
    "../js/tissues/view.js",
    "../js/tissues/list.js",
    "../js/tissues/thread.js",
    "../js/tissues/composer.js",
    "../js/tissues/rail.js",
    "../js/fixtures/cute-things.js",
  ];
  return files.map((file) => readFileSync(join(here, file), "utf8")).join("\n");
}

test("inbox organ renders four panes and an ink selected bar", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  const snap = await organ.ready();
  assert.equal(snap.panes.views && snap.panes.list && snap.panes.thread && snap.panes.rail, true);
  assert.match(snap.html, /data-pane="views"/);
  assert.match(snap.html, /data-pane="list"/);
  assert.match(snap.html, /data-pane="thread"/);
  assert.match(snap.html, /data-pane="rail"/);
  assert.doesNotMatch(snap.html, /data-pane="icons"|fifth-column/);
  assert.match(snap.html, /data-view="mine"/);
  assert.match(snap.html, /ticket-bar/);
  assert.equal(snap.selectedHasInkBar, true);
  assert.equal(snap.selectedId, "t-ada-track");
  assert.match(snap.html, /Ada Demo/);
  assert.match(snap.html, /#1002 · Paid · Fulfilled/);
});

test("Send stays disabled until the body has text", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  let snap = await organ.ready();
  assert.equal(snap.sendDisabled, true);
  organ.setBody("   ");
  snap = organ.snapshot();
  assert.equal(snap.sendDisabled, true);
  organ.setBody("Thanks Ada — checking the carrier now.");
  snap = organ.snapshot();
  assert.equal(snap.sendDisabled, false);
});

test("closed ticket keeps composer and hides Send & close", async () => {
  const organ = createInboxOrgan({ viewId: "closed", ticketId: "t-ada-closed" });
  const snap = await organ.ready();
  assert.equal(snap.hideSendAndClose, true);
  assert.match(snap.html, /data-composer/);
  assert.match(snap.html, />Send</);
  assert.doesNotMatch(snap.html, /Send &amp; close/);
});

test("no Edit, Refund, Cancel controls and no Gaia", async () => {
  const organ = createInboxOrgan({ viewId: "all" });
  const snap = await organ.ready();
  assert.deepEqual(snap.forbidden, []);
  assert.doesNotMatch(snap.html, /Gaia/i);
  assert.doesNotMatch(snap.html, /Ask Gaia/i);
  const tree = sourceTree();
  assert.doesNotMatch(tree, /Gaia/i);
  assert.doesNotMatch(tree, /Malky|Rivky|Sperber|Morgenstern/i);
  assert.doesNotMatch(tree, /#6B46C1|#7C3AED|#5B21B6|purple/i);
  assert.doesNotMatch(tree, /SHOPIFY_MUTATIONS_ENABLED\s*=\s*['"]?1/);
});

test("one rail tissue error leaves thread and other rail sections up", async () => {
  const shop = createFixtureShop({ fail: { returns: "fixture returns down" } });
  const organ = createInboxOrgan({ shop, viewId: "mine" });
  const snap = await organ.ready();
  assert.match(snap.html, /Where is my order #1002/);
  assert.match(snap.html, /data-tissue="customer"/);
  assert.match(snap.html, /Ada Demo/);
  assert.match(snap.html, /data-tissue="order"/);
  assert.match(snap.html, /Handcrafted Wooden Teether Toy/);
  assert.match(snap.html, /data-tissue="returns"/);
  assert.match(snap.html, /Returns error|fixture returns down/);
  assert.equal(snap.rail.models.customer.ok, true);
  assert.equal(snap.rail.models.order.ok, true);
  assert.equal(snap.rail.models.returns.ok, false);
  assert.ok(snap.html.includes("data-tissue=\"order-history\""));
});

test("Jordan ticket without an order does not blank the thread", async () => {
  const organ = createInboxOrgan({ viewId: "snoozed", ticketId: "t-jordan-ship" });
  const snap = await organ.ready();
  assert.match(snap.html, /Jordan Preview/);
  assert.match(snap.html, /Do you ship the demo catalog to Canada/);
  assert.match(snap.html, /No order on this ticket/);
  assert.equal(snap.rail.models.order.ok, false);
  assert.equal(snap.rail.models.customer.ok, true);
  assert.equal(snap.rail.currentOrderId, null);
});

test("history peek does not swap the open order", async () => {
  const organ = createInboxOrgan({ viewId: "unassigned", ticketId: "t-casey-hat" });
  const snap = await organ.ready();
  assert.equal(snap.rail.currentOrderId, IDS.ORDER_1003);
  assert.equal(snap.rail.models.order.record.name, "#1003");
  assert.deepEqual(snap.rail.models.history.rows.map((row) => row.name), ["#1004", "#1003"]);
});
