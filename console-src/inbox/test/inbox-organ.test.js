import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { IDS, tickets as fixtureTickets } from "../js/fixtures/demo-inbox.js";
import { createInboxOrgan } from "../js/inbox.js";
import { createMailbox } from "../js/mailbox.js";
import { createFixtureShop } from "../js/shop/fixture-shop.js";
import { createComposerTissue } from "../js/tissues/composer.js";
import { MAILBOX_TOPICS } from "../js/contracts.js";
import { railWriteControlHits } from "../js/util.js";

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
    "../js/tissues/customer.js",
    "../js/tissues/returns.js",
    "../js/tissues/order.js",
    "../js/shop/helpdesk-shop.js",
    "../js/shop/helpdesk-client.js",
    "../js/shop/helpdesk-tools.js",
    "../js/fixtures/demo-inbox.js",
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
  assert.match(snap.html, /#1001 · Paid · Fulfilled/);
  assert.match(snap.html, /Skip to thread\./);
  assert.match(snap.html, /<h2>Customer<\/h2>/);
  assert.match(snap.html, /<h3>Addresses<\/h3>/);
});

test("discarding the AI strip does not restore the draft", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  let snap = await organ.ready();
  assert.match(snap.html, /data-draft-strip/);
  const stripAt = snap.html.indexOf("data-draft-strip");
  const bodyAt = snap.html.indexOf("data-body");
  assert.ok(stripAt > -1 && bodyAt > stripAt, "draft strip sits above the textarea");
  const stripHtml = snap.html.slice(stripAt, bodyAt);
  assert.match(stripHtml, /data-insert/);
  assert.match(stripHtml, /data-discard/);
  assert.doesNotMatch(stripHtml, />Send</);
  organ.discardStrip();
  snap = organ.snapshot();
  assert.doesNotMatch(snap.html, /data-draft-strip/);
  assert.equal(snap.sendDisabled, true);
});

test("Send is ink primary and Send & close is hairline secondary", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  const snap = await organ.ready();
  const buttons = [...snap.html.matchAll(/<button\b[^>]*>/g)].map((match) => match[0]);
  const send = buttons.find((html) => /\bdata-send\b/.test(html) && !/\bdata-send-close\b/.test(html));
  const sendClose = buttons.find((html) => /\bdata-send-close\b/.test(html));
  assert.ok(send, "primary Send is present");
  assert.ok(sendClose, "Send & close is present on an open ticket");
  assert.match(send, /btn-ink/);
  assert.match(send, /btn-send/);
  assert.match(sendClose, /btn-hairline/);
  assert.doesNotMatch(sendClose, /btn-ink/);
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
  assert.doesNotMatch(snap.html, /data-send-close/);
});

test("no Edit, Refund, Cancel controls and no Gaia", async () => {
  const organ = createInboxOrgan({ viewId: "all" });
  const snap = await organ.ready();
  assert.deepEqual(snap.forbidden, []);
  assert.deepEqual(railWriteControlHits(snap.html), []);
  assert.doesNotMatch(snap.html, /<(button|a)\b[^>]*>\s*(?:Customer\s+)?Edit\b/i);
  assert.doesNotMatch(snap.html, /Gaia/i);
  assert.doesNotMatch(snap.html, /Ask Gaia/i);
  const tree = sourceTree();
  assert.doesNotMatch(tree, /Gaia/i);
  assert.doesNotMatch(tree, /Malky|Rivky|Sperber|Morgenstern/i);
  assert.doesNotMatch(tree, /#6B46C1|#7C3AED|#5B21B6|purple/i);
  assert.doesNotMatch(tree, /SHOPIFY_MUTATIONS_ENABLED\s*=\s*['"]?1/);
  assert.doesNotMatch(tree, /<(button|a)\b[^>]*>\s*(?:Customer\s+)?Edit\b/i);
  assert.doesNotMatch(tree, /customerUpdate|addressUpdate|customer_update/i);
  assert.doesNotMatch(tree, /\bdata-edit\b/);
});

test("one rail tissue error leaves thread and other rail sections up", async () => {
  const shop = createFixtureShop({ fail: { returns: "fixture returns down" } });
  const organ = createInboxOrgan({ shop, viewId: "mine" });
  const snap = await organ.ready();
  assert.match(snap.html, /Where is my order #1001/);
  assert.match(snap.html, /data-tissue="customer"/);
  assert.match(snap.html, /Ada Demo/);
  assert.match(snap.html, /data-tissue="order"/);
  assert.match(snap.html, /Oak Demo Rattle/);
  assert.match(snap.html, /data-tissue="returns"/);
  assert.match(snap.html, /Couldn(?:'|&#39;)t load Returns\. Retry\./);
  assert.match(snap.html, /data-retry="returns"/);
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

test("switching tickets resets rail expand and does not leak Ada OPEN returns", async () => {
  const organ = createInboxOrgan({ viewId: "all", ticketId: "t-ada-track" });
  await organ.ready();
  assert.equal(organ.snapshot().rail.open.returns, true);
  organ.toggleRail("returns");
  organ.toggleRail("order-history");
  assert.equal(organ.snapshot().rail.open.returns, false);
  assert.equal(organ.snapshot().rail.open["order-history"], true);

  await organ.selectTicket("t-casey-visor");
  let snap = organ.snapshot();
  assert.equal(snap.selectedId, "t-casey-visor");
  assert.equal(snap.rail.open.returns, false);
  assert.equal(snap.rail.open["order-history"], false);
  assert.equal(snap.rail.open.customer, true);
  assert.equal(snap.rail.open.order, true);
  assert.equal(snap.rail.open.addresses, false);
  assert.match(snap.html, /<h2>Returns<\/h2>\s*<span class="peek">No returns<\/span>/);

  await organ.selectTicket("t-jordan-ship");
  snap = organ.snapshot();
  assert.equal(snap.rail.open.returns, false);
  assert.match(snap.html, /No returns/);

  await organ.selectTicket("t-ada-track");
  snap = organ.snapshot();
  assert.equal(snap.rail.open.returns, true);
  assert.equal(snap.rail.open["order-history"], false);
  assert.match(snap.html, /In transit · 1 item/);
});

test("composer Insert and Discard never publish send", () => {
  const mailbox = createMailbox();
  const events = [];
  mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_SEND, (payload) => events.push(["send", payload]));
  mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_INSERT, (payload) => events.push(["insert", payload]));
  mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_DISCARD, () => events.push(["discard"]));
  const composer = createComposerTissue({ mailbox });
  const ticket = fixtureTickets[0];
  composer.update({ ticket, strip: ticket.stubDraft, body: "" });
  const el = { innerHTML: "", querySelector() { return null; } };
  composer.mount(el);
  el.onclick({ target: { closest: (sel) => (sel === "[data-insert]" ? {} : null) } });
  assert.equal(composer.sendDisabled(), false);
  assert.deepEqual(events.map((row) => row[0]), ["insert"]);
  el.onclick({ target: { closest: (sel) => (sel === "[data-discard]" ? {} : null) } });
  assert.deepEqual(events.map((row) => row[0]), ["insert", "discard"]);
  assert.ok(events.every((row) => row[0] !== "send"));
});

test("Insert puts the draft in the textarea and does not send", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  let snap = await organ.ready();
  assert.match(snap.html, /data-draft-strip/);
  assert.match(snap.html, /draft-kicker">AI draft</);
  assert.doesNotMatch(snap.html.slice(snap.html.indexOf("data-draft-strip"), snap.html.indexOf("data-body")), />Send</);
  assert.equal(snap.sendDisabled, true);
  assert.equal(snap.sent.length, 0);
  organ.insertDraft();
  snap = organ.snapshot();
  assert.doesNotMatch(snap.html, /data-draft-strip/);
  assert.match(snap.html, /Hi Ada/);
  assert.equal(snap.sendDisabled, false);
  assert.equal(snap.sent.length, 0);
});

test("Summarize fills a mute peek and does not enable Send", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  let snap = await organ.ready();
  assert.doesNotMatch(snap.html, /data-summarize-peek/);
  assert.match(snap.html, /Summarize 2 messages/);
  snap = await organ.requestSummarize();
  assert.match(snap.html, /data-summarize-peek/);
  assert.match(snap.html, /Ada asked/);
  assert.doesNotMatch(snap.html, /data-pane="ai"|ai-sidebar|fifth-column|Ask Gaia/i);
  assert.equal(snap.sendDisabled, true);
  assert.equal(snap.sent.length, 0);
  assert.match(snap.html, /Summarize 2 messages/);
});

test("history peek does not swap the open order", async () => {
  const organ = createInboxOrgan({ viewId: "unassigned", ticketId: "t-casey-visor" });
  const snap = await organ.ready();
  assert.equal(snap.rail.currentOrderId, IDS.ORDER_1002);
  assert.equal(snap.rail.models.order.record.name, "#1002");
  assert.deepEqual(snap.rail.models.history.rows.map((row) => row.name), ["#1003", "#1002"]);
});
