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
    "../js/shop/clerk-ticket.js",
    "../js/fixtures/demo-inbox.js",
  ];
  return files.map((file) => readFileSync(join(here, file), "utf8")).join("\n");
}

function fakeRoot() {
  const nodes = new Map();
  return {
    innerHTML: "",
    querySelector(sel) {
      if (!nodes.has(sel)) {
        nodes.set(sel, { innerHTML: "", querySelector() { return null; } });
      }
      return nodes.get(sel);
    },
    _node(sel) {
      return nodes.get(sel);
    },
  };
}

test("mount first-paints the Ada draft strip above the composer box", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  const root = fakeRoot();
  await organ.mount(root);
  const composer = root._node("[data-slot=composer]").innerHTML;
  assert.match(composer, /data-draft-strip/);
  assert.match(composer, /data-insert/);
  assert.match(composer, /data-discard/);
  assert.match(composer, /AI draft/);
  assert.match(composer, /disabled/);
  const stripAt = composer.indexOf("data-draft-strip");
  const boxAt = composer.indexOf("composer-box");
  const bodyAt = composer.indexOf("data-body");
  assert.ok(stripAt > -1 && boxAt > stripAt, "draft strip sits above the composer box");
  assert.ok(bodyAt > boxAt, "textarea stays inside the composer box");
  assert.doesNotMatch(composer.slice(boxAt), /data-draft-strip/);
});

test("selected list row CSS is a 4px ink bar with no wash", () => {
  const css = readFileSync(join(here, "../styles.css"), "utf8");
  assert.match(css, /--ink:\s*#1C1916/);
  assert.match(css, /\.ticket-row \.ticket-bar[\s\S]*width:\s*4px/);
  assert.match(css, /\.ticket-row\.is-selected\s*\{[^}]*background:\s*var\(--surface\)/);
  assert.match(css, /One leading-edge ink bar on the selected ticket \(4px\)/);
  assert.match(css, /\.track-link\s*\{[^}]*color:\s*var\(--accent\)/);
  assert.match(css, /\.invoice-link\s*\{[^}]*color:\s*var\(--accent\)/);
  assert.doesNotMatch(css, /\.track-link\s*\{[^}]*font-family:\s*var\(--mono\)/);
  assert.match(css, /\.ship-company\s*\{[^}]*color:\s*var\(--mute\)/);
  assert.match(css, /\.ship-number\s*\{[^}]*font-family:\s*var\(--mono\)/);
  assert.doesNotMatch(css, /\.ticket-row\.is-selected\s*\{[^}]*background:\s*(?:#e|#E|rgba?\(\s*\d+)/);
  assert.doesNotMatch(css, /\.ticket-row\.is-selected\s*\{[^}]*box-shadow:\s*inset/);
  assert.doesNotMatch(css, /#6B46C1|#7C3AED|#5B21B6/);
});

test("unsubscribe ticket shows mute request type without a Shopify write control", async () => {
  const organ = createInboxOrgan({ viewId: "mine", ticketId: "t-priya-unsub" });
  const snap = await organ.ready();
  assert.equal(snap.selectedId, "t-priya-unsub");
  assert.match(snap.html, /data-ticket="t-priya-unsub"[^>]*data-request-type="marketing_unsubscribe"/);
  assert.match(snap.html, /class="ticket-status ticket-request"[^>]*>Unsubscribe</);
  assert.match(snap.html, /class="thread-request mute"[^>]*>Marketing unsubscribe</);
  assert.match(snap.html, /data-tissue="preference"[^>]*data-request-type="marketing_unsubscribe"/);
  assert.match(snap.html, /<h2>Marketing unsubscribe<\/h2>/);
  assert.match(snap.html, /No Shopify write — confirm preference out of band/);
  assert.match(snap.html, /<h2>Customer<\/h2>\s*<span class="peek">No customer<\/span>/);
  assert.doesNotMatch(snap.html, /data-marketing-unsubscribe/);
  assert.doesNotMatch(snap.html, /<(button|a)\b[^>]*>[^<]*Unsubscribe/i);
  assert.deepEqual(snap.forbidden, []);
  const ada = await createInboxOrgan({ viewId: "mine", ticketId: "t-ada-track" }).ready();
  assert.doesNotMatch(ada.html, /data-ticket="t-ada-track"[^>]*data-request-type/);
  assert.doesNotMatch(ada.html, /data-tissue="preference"/);
});

test("privacy ticket shows mute request type without a Shopify write control", async () => {
  const organ = createInboxOrgan({ viewId: "mine", ticketId: "t-lee-privacy" });
  const snap = await organ.ready();
  assert.equal(snap.selectedId, "t-lee-privacy");
  assert.match(snap.html, /data-ticket="t-lee-privacy"[^>]*data-request-type="privacy_request"/);
  assert.match(snap.html, /class="ticket-status ticket-request"[^>]*>Privacy</);
  assert.match(snap.html, /class="thread-request mute"[^>]*>Privacy request</);
  assert.match(snap.html, /data-tissue="preference"[^>]*data-request-type="privacy_request"/);
  assert.match(snap.html, /<h2>Privacy request<\/h2>\s*<span class="peek">Delete<\/span>/);
  assert.match(snap.html, /Privacy tools stay locked\. No live data erase or export\./);
  assert.match(snap.html, /data-privacy-gate-open>Mark privacy handled</);
  assert.match(snap.html, /<h2>Customer<\/h2>\s*<span class="peek">No customer<\/span>/);
  assert.doesNotMatch(snap.html, /data-tissue="privacy"/);
  assert.doesNotMatch(snap.html, /data-customer-privacy/);
  assert.doesNotMatch(snap.html, /<(button|a)\b[^>]*>[^<]*(?:erasure|redact|Customer Privacy)/i);
  assert.deepEqual(snap.forbidden, []);
  const gated = organ.openPrivacyGate();
  assert.match(gated.html, /data-privacy-gate/);
  assert.match(gated.html, /Privacy tools stay locked\. No live data erase or export\./);
  const handled = await organ.markPrivacyHandled();
  assert.match(handled.html, /Privacy handled/);
  assert.doesNotMatch(handled.html, /data-privacy-gate-open/);
  const priya = await createInboxOrgan({ viewId: "mine", ticketId: "t-priya-unsub" }).ready();
  assert.match(priya.html, /data-ticket="t-priya-unsub"[^>]*data-request-type="marketing_unsubscribe"/);
  assert.match(priya.html, /class="ticket-status ticket-request"[^>]*>Unsubscribe</);
});

test("list rows show helpdesk status open closed snoozed", async () => {
  const snap = await createInboxOrgan({ viewId: "all" }).ready();
  assert.match(snap.html, /data-ticket="t-ada-track"[^>]*data-status="open"/);
  assert.match(snap.html, /data-ticket="t-ada-closed"[^>]*data-status="closed"/);
  assert.match(snap.html, /data-ticket="t-jordan-ship"[^>]*data-status="snoozed"/);
  assert.match(snap.html, /class="ticket-status">Open</);
  assert.match(snap.html, /class="ticket-status">Closed</);
  assert.match(snap.html, /class="ticket-status">Snoozed</);
  assert.doesNotMatch(snap.html, /class="ticket-status">OPEN</);
  assert.doesNotMatch(snap.html, /class="ticket-status">CLOSED</);
  assert.doesNotMatch(snap.html, /class="ticket-status">SNOOZED</);
});

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
  assert.match(snap.html, /data-line-fulfill="Shipped">Shipped</);
  assert.match(snap.html, /<h3>Shipment<\/h3>\s*<span class="peek">In transit<\/span>/);
  assert.match(snap.html, /<span class="ship-company">Demo Carrier<\/span>/);
  assert.match(snap.html, /<span class="mono ship-number">DEMO-1001<\/span>/);
  assert.match(snap.html, /<a class="track-link"[^>]*>Track<\/a>/);
  assert.doesNotMatch(snap.html, /<a class="track-link"[^>]*>Demo Carrier/);
  assert.match(snap.html, /Skip to thread\./);
  assert.match(snap.html, /<h2>Customer<\/h2>/);
  assert.match(snap.html, /<h3>Gift cards<\/h3>\s*<span class="peek">••••4291<\/span>/);
  assert.match(snap.html, /25\.00 USD · Enabled/);
  assert.match(snap.html, /<h3>Discounts<\/h3>\s*<span class="peek">WELCOME10<\/span>/);
  assert.match(snap.html, /<p class="mono discount-code">WELCOME10<\/p>/);
  assert.match(snap.html, /<h3>Invoice<\/h3>\s*<span class="peek">Invoice<\/span>/);
  assert.match(snap.html, /<a class="invoice-link"[^>]*>Invoice<\/a>/);
  assert.match(snap.html, /<h3>Warranty<\/h3>\s*<span class="peek">1 year · Active<\/span>/);
  assert.match(snap.html, /<p class="mute warranty-line">Ends 12 Mar 2027<\/p>/);
  assert.match(snap.html, /<h3>ETA<\/h3>\s*<span class="peek">ETA Tue 8 Sep<\/span>/);
  assert.match(snap.html, /<p class="mute eta-line">Zone: Domestic<\/p>/);
  assert.match(snap.html, /<h3>Addresses<\/h3>/);
  assert.match(snap.html, /ticket-row is-selected/);
  assert.match(snap.html, /status-line">Open · Friday/);
  assert.doesNotMatch(snap.html, /Assigned to me ·/);
});

test("partial-ship ticket shows mixed lines on the order rail", async () => {
  const organ = createInboxOrgan({ viewId: "unassigned", ticketId: "t-sky-rest" });
  const snap = await organ.ready();
  assert.equal(snap.selectedId, "t-sky-rest");
  assert.match(snap.html, /#9004 · Paid · Partially Fulfilled/);
  assert.match(snap.html, /data-line-fulfill="Shipped">Shipped</);
  assert.match(snap.html, /data-line-fulfill="Unfulfilled">Unfulfilled</);
  assert.match(snap.html, /Muslin Swaddle/);
  assert.match(snap.html, /Knit Baby Booties/);
  assert.match(snap.html, /<span class="ship-company">Sample Carrier<\/span>/);
  assert.match(snap.html, /<span class="mono ship-number">SAMPLE-9004<\/span>/);
  assert.match(snap.html, /<a class="track-link"[^>]*>Track<\/a>/);
  assert.doesNotMatch(snap.html, /<a class="track-link"[^>]*>Sample Carrier/);
  assert.match(snap.html, /<h3>Shipment<\/h3>\s*<span class="peek">In transit<\/span>/);
  assert.doesNotMatch(snap.html, /<p class="tissue-empty">No tracking<\/p>/);
});

test("closed Ada thread mutes Closed · Tuesday", async () => {
  const organ = createInboxOrgan({ viewId: "closed", ticketId: "t-ada-closed" });
  const snap = await organ.ready();
  assert.equal(snap.selectedId, "t-ada-closed");
  assert.equal(snap.selectedHasInkBar, true);
  assert.match(snap.html, /status-line">Closed · Tuesday/);
  assert.match(snap.html, /#1001 · Paid · Fulfilled/);
  assert.doesNotMatch(snap.html, /#1002 ·/);
  assert.doesNotMatch(snap.html, /Set status: closed/);
  assert.doesNotMatch(snap.html, /displayFulfillmentStatus/);
  assert.match(snap.html, /btn-quiet" data-summarize/);
  const stripAt = snap.html.indexOf("data-draft-strip");
  const bodyAt = snap.html.indexOf("data-body");
  if (stripAt > -1 && bodyAt > stripAt) {
    assert.doesNotMatch(snap.html.slice(stripAt, bodyAt), />Send</);
  }
});

test("Ada inbound From is the customer persona, not teddyjubu", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  const snap = await organ.ready();
  assert.match(snap.html, /<strong>From Ada Demo<\/strong>/);
  assert.match(snap.html, /<strong>From Demo Shop<\/strong>/);
  assert.match(snap.html, /status-line">Open · Friday/);
  assert.doesNotMatch(snap.html, /From teddyjubu/i);
  assert.doesNotMatch(snap.html, /teddyjubu@agentmail\.to/i);
  const inboundAt = snap.html.indexOf("From Ada Demo");
  const agentAt = snap.html.indexOf("From Demo Shop");
  assert.ok(inboundAt > -1 && agentAt > inboundAt, "customer From precedes staff From");
});

test("staff outbound From stays the shop identity and does not pretend to be the customer", async () => {
  const ada = fixtureTickets.find((ticket) => ticket.id === "t-ada-track");
  const organ = createInboxOrgan({
    viewId: "mine",
    ticketId: "t-ada-track",
    tickets: [{
      ...ada,
      messages: [
        ...ada.messages,
        {
          id: "out-1",
          from: "agent",
          fromAgent: true,
          fromName: "Demo Shop",
          name: "Demo Shop",
          at: "2026-08-28T15:00:00Z",
          body: "Checking the carrier now, Ada.",
        },
      ],
    }],
  });
  const snap = await organ.ready();
  assert.match(snap.html, /<strong>From Ada Demo<\/strong>/);
  const agentHits = [...snap.html.matchAll(/<strong>From Demo Shop<\/strong>/g)];
  assert.ok(agentHits.length >= 2, "staff From stays Demo Shop on outbound");
  assert.match(snap.html, /Checking the carrier now, Ada/);
  assert.doesNotMatch(snap.html, /From teddyjubu/i);
});

test("discarding the AI strip does not restore the draft", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  let snap = await organ.ready();
  assert.match(snap.html, /data-draft-strip/);
  const stripAt = snap.html.indexOf("data-draft-strip");
  const boxAt = snap.html.indexOf("composer-box");
  const bodyAt = snap.html.indexOf("data-body");
  assert.ok(stripAt > -1 && boxAt > stripAt, "draft strip sits above the composer box");
  assert.ok(bodyAt > boxAt, "textarea stays inside the composer box");
  const stripHtml = snap.html.slice(stripAt, boxAt);
  assert.match(stripHtml, /data-insert/);
  assert.match(stripHtml, /data-discard/);
  assert.doesNotMatch(stripHtml, />Send</);
  assert.doesNotMatch(snap.html.slice(boxAt, bodyAt), /data-draft-strip/);
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
  const emptySend = [...snap.html.matchAll(/<button\b[^>]*>/g)]
    .map((match) => match[0])
    .find((html) => /\bdata-send\b/.test(html) && !/\bdata-send-close\b/.test(html));
  assert.ok(emptySend, "Send is present on an empty box");
  assert.match(emptySend, /\bdisabled\b/);
  assert.match(emptySend, /is-disabled/);
  const css = readFileSync(join(here, "../styles.css"), "utf8");
  assert.match(css, /\.btn-send:disabled[\s\S]*background:\s*var\(--ground\)/);
  assert.match(css, /\.btn-send:disabled[\s\S]*color:\s*var\(--mute\)/);
  organ.setBody("   ");
  snap = organ.snapshot();
  assert.equal(snap.sendDisabled, true);
  const blankSend = [...snap.html.matchAll(/<button\b[^>]*>/g)]
    .map((match) => match[0])
    .find((html) => /\bdata-send\b/.test(html) && !/\bdata-send-close\b/.test(html));
  assert.match(blankSend, /\bdisabled\b/);
  assert.match(blankSend, /is-disabled/);
  organ.setBody("Thanks Ada — checking the carrier now.");
  snap = organ.snapshot();
  assert.equal(snap.sendDisabled, false);
  const readySend = [...snap.html.matchAll(/<button\b[^>]*>/g)]
    .map((match) => match[0])
    .find((html) => /\bdata-send\b/.test(html) && !/\bdata-send-close\b/.test(html));
  assert.doesNotMatch(readySend, /\bdisabled\b/);
  assert.doesNotMatch(readySend, /is-disabled/);
});

test("thread header shows Escalate as a secondary control", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  const snap = await organ.ready();
  assert.match(snap.html, /data-escalate="t-ada-track"/);
  assert.match(snap.html, />Escalate</);
  assert.match(snap.html, /thread-head-actions/);
  const escalate = [...snap.html.matchAll(/<button\b[^>]*>/g)]
    .map((match) => match[0])
    .find((html) => /\bdata-escalate\b/.test(html));
  assert.ok(escalate, "Escalate lives in the thread header");
  assert.match(escalate, /btn-quiet/);
  assert.doesNotMatch(escalate, /btn-ink/);
});

test("composer shows write-gate copy without Refund or Cancel controls", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  const snap = await organ.ready();
  assert.ok(fixtureTickets[0].orderId, "Ada fixture is joined to an order");
  assert.match(snap.html, /data-write-gate/);
  assert.match(snap.html, /Refunds and cancels are gated/);
  assert.deepEqual(snap.forbidden, []);
  assert.doesNotMatch(snap.html, /<(button|a)\b[^>]*>[^<]*Refund/i);
  assert.doesNotMatch(snap.html, /<(button|a)\b[^>]*>[^<]*\bCancel\b/i);
});

test("composer write-gate copy is gated on orderId", async () => {
  const withOrder = createInboxOrgan({ viewId: "mine", ticketId: "t-ada-track" });
  const joined = await withOrder.ready();
  assert.match(joined.html, /data-write-gate>/);
  assert.match(joined.html, /Refunds and cancels are gated/);

  const noOrder = createInboxOrgan({ viewId: "snoozed", ticketId: "t-jordan-ship" });
  const empty = await noOrder.ready();
  assert.equal(empty.rail.currentOrderId, null);
  assert.match(empty.html, /No order on this ticket/);
  assert.doesNotMatch(empty.html, /data-write-gate>/);
  assert.doesNotMatch(empty.html, /Refunds and cancels are gated/);
});

test("composer write-gate note requires ticket orderId", () => {
  const mailbox = createMailbox();
  const composer = createComposerTissue({ mailbox });
  const writeGate = { mutationsEnabled: false, refused: ["refund", "cancel"] };
  const ada = fixtureTickets.find((ticket) => ticket.id === "t-ada-track");
  composer.update({ ticket: ada, writeGate });
  assert.match(composer.render(), /data-write-gate/);
  assert.match(composer.render(), /Refunds and cancels are gated/);

  composer.update({ ticket: { ...ada, orderId: null }, writeGate });
  assert.doesNotMatch(composer.render(), /data-write-gate/);
  assert.doesNotMatch(composer.render(), /Refunds and cancels are gated/);
});

test("escalate marks the ticket and does not Send", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  await organ.ready();
  const snap = await organ.escalate("pending review");
  assert.match(snap.html, /status-line"[^>]*data-escalated[^>]*>Escalated · /);
  assert.doesNotMatch(snap.html, /status-badge[^>]*>Escalated</);
  assert.doesNotMatch(snap.html, /data-escalate=/);
  assert.equal(snap.sent.length, 0);
});

test("This order hairline opens the payments lock sheet", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  let snap = await organ.ready();
  assert.match(snap.html, /data-tissue="order"/);
  const locked = [...snap.html.matchAll(/<button\b[^>]*>/g)]
    .map((match) => match[0])
    .find((html) => /\bdata-write-gate-open\b/.test(html));
  assert.ok(locked, "Payments locked hairline lives on This order");
  assert.match(locked, /btn-hairline/);
  assert.match(snap.html, />Payments locked</);
  assert.doesNotMatch(snap.html, /data-gate-sheet/);
  snap = organ.openWriteGate();
  assert.match(snap.html, /data-gate-sheet/);
  assert.match(snap.html, /Payments are locked until Syeed names an exact write/);
  assert.match(snap.html, /Refunds and cancels stay refused/);
  assert.deepEqual(snap.forbidden, []);
  assert.doesNotMatch(snap.html, /<(button|a)\b[^>]*>[^<]*Refund/i);
  assert.doesNotMatch(snap.html, /<(button|a)\b[^>]*>[^<]*\bCancel\b/i);
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

test("boot only pulls mailbox when ?pull=1", () => {
  const boot = readFileSync(join(here, "../js/boot.js"), "utf8");
  assert.match(boot, /params\.get\("pull"\)\s*===\s*"1"/);
  assert.doesNotMatch(boot, /await organ\.pullMailbox\(\{ limit:[^}]+\}\);\s*organ\.mount/);
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

test("Sam unjoined ticket with null GIDs says No customer on this ticket", async () => {
  const organ = createInboxOrgan({
    viewId: "unassigned",
    ticketId: "t-sam-unjoined",
    tickets: [{
      id: "t-sam-unjoined",
      customerName: "Sam",
      subject: "Broken rattle",
      snippet: "The wooden rattle arrived cracked. Can you help?",
      status: "open",
      view: "unassigned",
      assignee: null,
      customerId: null,
      orderId: null,
      updatedAt: "2026-08-30T14:10:00Z",
      messages: [{
        id: "m-sam",
        fromAgent: false,
        name: "Sam",
        at: "2026-08-30T14:10:00Z",
        body: "The wooden rattle arrived cracked. Can you help?",
      }],
      statusEvents: [],
    }],
  });
  const snap = await organ.ready();
  assert.equal(snap.selectedId, "t-sam-unjoined");
  assert.match(snap.html, /<h2>Customer<\/h2>\s*<span class="peek">No customer<\/span>/);
  assert.match(snap.html, /No customer on this ticket/);
  assert.doesNotMatch(snap.html, /Customer unavailable/);
  assert.match(snap.html, /No order on this ticket/);
  assert.match(snap.html, /<strong>From Sam<\/strong>/);
  assert.doesNotMatch(snap.html, /From teddyjubu/i);
  assert.match(snap.html, /ticket-name">Sam</);
  assert.equal(snap.rail.models.customer.ok, false);
  assert.equal(snap.rail.models.customer.record, null);
  assert.equal(snap.rail.currentOrderId, null);
});

test("inbound From falls back to ticket customerName when message name is the mailbox login", async () => {
  const organ = createInboxOrgan({
    viewId: "unassigned",
    ticketId: "t-ada-mailbox-from",
    tickets: [{
      id: "t-ada-mailbox-from",
      customerName: "Ada",
      subject: "Tracking on order #1001 has not moved",
      snippet: "Where is my order #1001?",
      status: "open",
      view: "unassigned",
      assignee: null,
      customerId: null,
      orderId: null,
      updatedAt: "2026-08-30T14:02:00Z",
      fromEmail: "teddyjubu@agentmail.to",
      messages: [{
        id: "m-ada-mailbox",
        from: "customer",
        fromAgent: false,
        name: "teddyjubu",
        fromEmail: "teddyjubu@agentmail.to",
        at: "2026-08-30T14:02:00Z",
        body: "Where is my order #1001? The tracking has not updated.",
      }],
      statusEvents: [],
    }],
  });
  const snap = await organ.ready();
  assert.match(snap.html, /<strong>From Ada<\/strong>/);
  assert.match(snap.html, /ticket-name">Ada</);
  assert.doesNotMatch(snap.html, /From teddyjubu/i);
  assert.doesNotMatch(snap.html, /teddyjubu@agentmail\.to/i);
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
  assert.match(snap.html, /<h3>Shipment<\/h3>\s*<span class="peek">No tracking<\/span>/);
  assert.equal(snap.rail.open.shipment, false);
  assert.equal(snap.rail.open.giftCards, false);
  assert.equal(snap.rail.open.discounts, false);
  assert.equal(snap.rail.open.invoice, false);
  assert.equal(snap.rail.open.warranty, false);
  assert.equal(snap.rail.open.eta, false);
  assert.match(snap.html, /<h3>Gift cards<\/h3>\s*<span class="peek">No gift cards<\/span>/);
  assert.match(snap.html, /<h3>Discounts<\/h3>\s*<span class="peek">No discounts<\/span>/);
  assert.match(snap.html, /<h3>Invoice<\/h3>\s*<span class="peek">No invoice<\/span>/);
  assert.match(snap.html, /<h3>Warranty<\/h3>\s*<span class="peek">No warranty<\/span>/);
  assert.match(snap.html, /<h3>ETA<\/h3>\s*<span class="peek">No ETA<\/span>/);

  await organ.selectTicket("t-jordan-ship");
  snap = organ.snapshot();
  assert.equal(snap.rail.open.returns, false);
  assert.match(snap.html, /No returns/);

  await organ.selectTicket("t-ada-track");
  snap = organ.snapshot();
  assert.equal(snap.rail.open.returns, true);
  assert.equal(snap.rail.open["order-history"], false);
  assert.equal(snap.rail.open.giftCards, true);
  assert.equal(snap.rail.open.discounts, true);
  assert.equal(snap.rail.open.invoice, true);
  assert.equal(snap.rail.open.warranty, true);
  assert.equal(snap.rail.open.eta, true);
  assert.match(snap.html, /In transit · 1 item/);
  assert.match(snap.html, /••••4291/);
  assert.match(snap.html, /WELCOME10/);
  assert.match(snap.html, /<a class="invoice-link"[^>]*>Invoice<\/a>/);
  assert.match(snap.html, /1 year · Active/);
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
  const stripAt = snap.html.indexOf("data-draft-strip");
  const boxAt = snap.html.indexOf("composer-box");
  assert.ok(stripAt > -1 && boxAt > stripAt, "draft strip sits above the composer box");
  assert.doesNotMatch(snap.html.slice(stripAt, boxAt), />Send</);
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

test("macro search lives in the composer box and Insert fills the textarea", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  let snap = await organ.ready();
  assert.match(snap.html, /data-macro-search/);
  assert.match(snap.html, /data-macro-list/);
  assert.match(snap.html, /data-macro-insert/);
  assert.match(snap.html, />Replace</);
  assert.match(snap.html, /data-macro-append/);
  assert.match(snap.html, /Shipping delay/);
  assert.match(snap.html, /Return how-to/);
  assert.match(snap.html, /Order status/);
  const boxStart = snap.html.indexOf("composer-box");
  const boxEnd = snap.html.indexOf("composer-actions");
  const box = snap.html.slice(boxStart, boxEnd);
  assert.match(box, /data-macro-search/);
  assert.match(box, /Shipping delay/);
  assert.doesNotMatch(box, /data-pane="ai"|floating-macro|macro-panel/);
  assert.equal(snap.sendDisabled, true);
  assert.equal(snap.sent.length, 0);

  snap = await organ.searchMacros("delay");
  assert.equal(snap.macros.length, 1);
  assert.equal(snap.macros[0].id, "shipping-delay");
  assert.match(snap.html, /Shipping delay/);
  assert.doesNotMatch(snap.html, /Return how-to/);
  assert.equal(snap.sendDisabled, true);

  snap = await organ.applyMacro("shipping-delay", "replace");
  assert.match(snap.html, /running behind the usual window/);
  assert.equal(snap.sendDisabled, false);
  assert.equal(snap.sent.length, 0);
  assert.match(snap.html, /data-macro-open="false"/);
  assert.doesNotMatch(snap.html, /data-macro-list/);
  assert.doesNotMatch(snap.html, /data-macro-insert/);
  assert.doesNotMatch(snap.html, />Replace</);
  const filledSend = [...snap.html.matchAll(/<button\b[^>]*>/g)]
    .map((match) => match[0])
    .find((html) => /\bdata-send\b/.test(html) && !/\bdata-send-close\b/.test(html));
  assert.doesNotMatch(filledSend, /\bdisabled\b/);

  organ.setBody("Hi Ada — looking now.");
  snap = await organ.applyMacro("order-status", "append");
  assert.match(snap.html, /Hi Ada — looking now/);
  assert.match(snap.html, /I looked at this order/);
  assert.equal(snap.sendDisabled, false);
  assert.equal(snap.sent.length, 0);
});

test("composer macro Insert and Append never publish send", () => {
  const mailbox = createMailbox();
  const events = [];
  mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_SEND, (payload) => events.push(["send", payload]));
  mailbox.subscribe(MAILBOX_TOPICS.COMPOSER_INSERT, (payload) => events.push(["insert", payload]));
  const composer = createComposerTissue({ mailbox });
  const ticket = fixtureTickets[0];
  composer.update({
    ticket,
    body: "",
    macros: [
      { id: "shipping-delay", title: "Shipping delay", tags: ["shipping"], body: "Hi — delay body." },
    ],
    selectedMacroId: "shipping-delay",
  });
  const el = { innerHTML: "", querySelector() { return null; } };
  composer.mount(el);
  el.onclick({ target: { closest: (sel) => (sel === "[data-macro-insert]" ? {} : null) } });
  assert.equal(composer.sendDisabled(), false);
  assert.deepEqual(events.map((row) => row[0]), ["insert"]);
  assert.equal(events[0][1].mode, "replace");
  assert.equal(events[0][1].macroId, "shipping-delay");
  composer.update({ searchOpen: true, selectedMacroId: "shipping-delay" });
  composer.mount(el);
  el.onclick({ target: { closest: (sel) => (sel === "[data-macro-append]" ? {} : null) } });
  assert.deepEqual(events.map((row) => row[0]), ["insert", "insert"]);
  assert.equal(events[1][1].mode, "append");
  assert.ok(events.every((row) => row[0] !== "send"));
});

test("history peek does not swap the open order", async () => {
  const organ = createInboxOrgan({ viewId: "unassigned", ticketId: "t-casey-visor" });
  const snap = await organ.ready();
  assert.equal(snap.rail.currentOrderId, IDS.ORDER_1002);
  assert.equal(snap.rail.models.order.record.name, "#1002");
  assert.deepEqual(snap.rail.models.history.rows.map((row) => row.name), ["#1003", "#1002"]);
});
