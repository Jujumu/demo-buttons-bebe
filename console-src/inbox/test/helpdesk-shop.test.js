import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { IDS, SHOP, tickets as fixtureTickets } from "../js/fixtures/demo-inbox.js";
import { createHelpdeskClient } from "../js/shop/helpdesk-client.js";
import { createHelpdeskShop, resolveLiveInbox } from "../js/shop/helpdesk-shop.js";
import { TOOL_NAMES, WRITE_TOOLS } from "../js/shop/helpdesk-tools.js";
import { LIVE_IDS, LIVE_SHOP, liveTickets } from "../js/shop/live-catalog.js";
import { createInboxOrgan } from "../js/inbox.js";
import { createFixtureShop } from "../js/shop/fixture-shop.js";
import { createMailbox } from "../js/mailbox.js";
import { createRailOrgan } from "../js/tissues/rail.js";
import { projectOrder } from "../js/tissues/order.js";
import { projectReturns } from "../js/tissues/returns.js";
import { projectOrderHistory } from "../js/tissues/order-history.js";

const here = dirname(fileURLToPath(import.meta.url));
const helpdeskRoot = join(here, "../../helpdesk-agent");
const python = process.env.PYTHON || "python3";

const SAMPLE_SHOP = "demo-helpdesk.example";
const SAMPLE_ADA = "gid://shopify/Customer/9001";
const SAMPLE_ADA_ORDER = "gid://shopify/Order/9001";
const SAMPLE_CASEY = "gid://shopify/Customer/9002";

function pythonInvoke(tool, args) {
  const argv = [python, "-m", "helpdesk"];
  if (tool === "helpdesk.list_tickets") {
    argv.push("list-tickets", "--view", String(args.view || "open"), "--limit", String(args.limit || 20));
  } else if (tool === "helpdesk.get_ticket") {
    argv.push("get-ticket", "--ticket-id", String(args.ticketId));
  } else if (tool === "helpdesk.get_customer") {
    argv.push("get-customer", "--shop", args.shop, "--customer-id", args.customerId);
  } else if (tool === "helpdesk.get_order") {
    argv.push("get-order", "--shop", args.shop, "--order-id", args.orderId);
  } else if (tool === "helpdesk.get_returns") {
    argv.push("get-returns", "--shop", args.shop, "--order-id", args.orderId);
  } else if (tool === "helpdesk.list_past_orders") {
    argv.push("list-past-orders", "--shop", args.shop, "--customer-id", args.customerId);
  } else if (tool === "helpdesk.draft_reply") {
    argv.push("draft-reply", "--ticket", String(args.ticketId));
    if (args.shop) argv.push("--shop", args.shop);
  } else if (tool === "helpdesk.summarize_thread") {
    argv.push("summarize-thread", "--ticket", String(args.ticketId));
    if (args.shop) argv.push("--shop", args.shop);
  } else {
    throw new Error(`unknown tool ${tool}`);
  }
  const result = spawnSync(argv[0], argv.slice(1), {
    cwd: helpdeskRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      PYTHONPATH: helpdeskRoot,
      HELPDESK_SOURCE: args._source || "sample",
    },
  });
  assert.equal(result.error, undefined, result.stderr);
  const payload = JSON.parse(result.stdout);
  payload._exit = result.status;
  return payload;
}

function clientFromPython(source = "sample") {
  return createHelpdeskClient({
    invoke(tool, args) {
      return pythonInvoke(tool, { ...args, _source: source });
    },
  });
}

test("client exposes exactly the eight helpdesk tools", () => {
  const client = createHelpdeskClient({ invoke: async () => ({ ok: true }) });
  assert.deepEqual(client.tools, TOOL_NAMES);
  assert.equal(TOOL_NAMES.length, 8);
  assert.ok(TOOL_NAMES.includes("helpdesk.draft_reply"));
  assert.ok(TOOL_NAMES.includes("helpdesk.summarize_thread"));
  assert.deepEqual([...WRITE_TOOLS], ["helpdesk.send", "helpdesk.refund", "helpdesk.cancel"]);
  for (const name of WRITE_TOOLS) {
    assert.ok(!TOOL_NAMES.includes(name));
  }
});

test("CLI payloads match the JS shop adapter for sample rail tools", async () => {
  const shop = createHelpdeskShop({ client: clientFromPython("sample"), shop: SAMPLE_SHOP });
  const customer = await shop.getCustomer({ shop: SAMPLE_SHOP, customerId: SAMPLE_ADA });
  assert.equal(customer.displayName, "Ada Demo");
  assert.equal(customer.defaultEmailAddress.emailAddress, "ada@demo-helpdesk.example");
  assert.equal(typeof customer.numberOfOrders, "string");
  assert.equal(customer.email, undefined);

  const order = await shop.getOrder({ shop: SAMPLE_SHOP, orderId: SAMPLE_ADA_ORDER });
  assert.equal(order.billingAddress, null);
  assert.equal(order.lineItems.nodes[0].sku, undefined);
  assert.ok(order.currentTotalPriceSet.shopMoney);
  const projected = projectOrder(order);
  assert.equal(projected.addressPeek, "No billing");
  assert.equal(projected.skuLabels[0], "");

  const returns = await shop.getReturns({ shop: SAMPLE_SHOP, orderId: SAMPLE_ADA_ORDER });
  assert.equal(returns.returns.nodes[0].status, "OPEN");
  assert.equal(returns.inProgress, true);
  assert.equal(returns.orderReturnStatus, "IN_PROGRESS");

  const history = await shop.getOrderHistory({ shop: SAMPLE_SHOP, customerId: SAMPLE_CASEY });
  assert.deepEqual(history.map((row) => row.name), ["#9003", "#9002"]);
  assert.ok(history[0].currentTotalPriceSet.shopMoney);
  assert.equal(history[0].total, undefined);
  assert.equal(projectOrderHistory(history).rows[0].fulfillmentStatus, history[0].displayFulfillmentStatus);
});

test("all eight CLI tools return ok on the same handler path", () => {
  const cases = [
    ["helpdesk.list_tickets", { view: "open", limit: 5 }],
    ["helpdesk.get_ticket", { ticketId: "1001" }],
    ["helpdesk.get_customer", { shop: SAMPLE_SHOP, customerId: SAMPLE_ADA }],
    ["helpdesk.get_order", { shop: SAMPLE_SHOP, orderId: SAMPLE_ADA_ORDER }],
    ["helpdesk.get_returns", { shop: SAMPLE_SHOP, orderId: SAMPLE_ADA_ORDER }],
    ["helpdesk.list_past_orders", { shop: SAMPLE_SHOP, customerId: SAMPLE_ADA }],
    ["helpdesk.draft_reply", { ticketId: "1001", shop: SAMPLE_SHOP }],
    ["helpdesk.summarize_thread", { ticketId: "1001" }],
  ];
  for (const [tool, args] of cases) {
    const payload = pythonInvoke(tool, args);
    assert.equal(payload.ok, true, tool);
    assert.equal(payload.tool, tool);
  }
});

test("live-holes returns stay empty and never inherit Ada OPEN", async () => {
  const shop = createHelpdeskShop({
    client: clientFromPython("live-holes"),
    shop: LIVE_SHOP,
  });
  const returns = await shop.getReturns({ shop: LIVE_SHOP, orderId: LIVE_IDS.O_1001 });
  assert.deepEqual(returns.returns.nodes, []);
  assert.equal(returns.inProgress, false);
  assert.equal(returns.orderReturnStatus, "NO_RETURN");
  assert.equal(projectReturns(returns).peek, "No returns");
  assert.equal(projectReturns(returns).collapsedDefault, true);

  const order = await shop.getOrder({ shop: LIVE_SHOP, orderId: LIVE_IDS.O_1001 });
  assert.equal(order.billingAddress, null);
  assert.equal(order.lineItems.nodes[0].sku, undefined);
  assert.equal(projectOrder(order).addressPeek, "No billing");
});

test("fixture fallback keeps Ada OPEN when helpdesk is down", async () => {
  const shop = createHelpdeskShop({
    client: createHelpdeskClient({
      invoke() {
        throw new Error("mint unavailable");
      },
    }),
  });
  const returns = await shop.getReturns({ shop: SHOP, orderId: IDS.ORDER_1001 });
  assert.equal(returns.returns.nodes[0].status, "OPEN");
  assert.equal(projectReturns(returns).peek, "In transit · 1 item");
  const customer = await shop.getCustomer({ shop: SHOP, customerId: IDS.ADA });
  assert.equal(customer.displayName, "Ada Demo");
});

test("default inbox organ still first-paints Ada fixtures when HTTP is down", async () => {
  const organ = createInboxOrgan({ viewId: "mine" });
  const snap = await organ.ready();
  assert.equal(snap.selectedId, "t-ada-track");
  assert.match(snap.html, /Ada Demo/);
  assert.match(snap.html, /In transit · 1 item/);
  assert.equal(snap.rail.open.returns, true);
  assert.equal(snap.rail.models.returns.record.returns.nodes[0].status, "OPEN");
});

test("live catalog has empty returns and does not replace This order on history peek", async () => {
  const shop = createHelpdeskShop({
    client: clientFromPython("live-holes"),
    shop: LIVE_SHOP,
  });
  const organ = createInboxOrgan({
    shop,
    shopHost: LIVE_SHOP,
    tickets: liveTickets,
    viewId: "unassigned",
    ticketId: "t-fulfilled",
  });
  const snap = await organ.ready();
  assert.equal(snap.rail.models.returns.inProgress, false);
  assert.equal(snap.rail.open.returns, false);
  assert.match(snap.html, /<h2>Returns<\/h2>\s*<span class="peek">No returns<\/span>/);
  assert.equal(snap.rail.models.order.record.name, "#1002");
  const names = snap.rail.models.history.rows.map((row) => row.name);
  assert.ok(names.includes("#1002"));
  assert.equal(snap.rail.currentOrderId, LIVE_IDS.O_1002);
});

test("ticket switch resets rail and does not leak a fixture OPEN onto live tickets", async () => {
  const fixtureShop = createFixtureShop();
  const liveShop = createHelpdeskShop({
    client: clientFromPython("live-holes"),
    shop: LIVE_SHOP,
  });
  const mailbox = createMailbox();
  const rail = createRailOrgan({ shop: fixtureShop, mailbox });
  await rail.load({ shop: SHOP, customerId: IDS.ADA, orderId: IDS.ORDER_1001, ticketId: "t-ada-track" });
  assert.equal(rail.snapshot().open.returns, true);

  const liveRail = createRailOrgan({ shop: liveShop, mailbox: createMailbox() });
  await liveRail.load({
    shop: LIVE_SHOP,
    customerId: LIVE_IDS.C_UNFULFILLED,
    orderId: LIVE_IDS.O_1001,
    ticketId: "t-unfulfilled",
  });
  assert.equal(liveRail.snapshot().open.returns, false);
  assert.equal(liveRail.snapshot().models.returns.inProgress, false);
  assert.equal(liveRail.snapshot().models.returns.peek, "No returns");
});

test("one helpdesk tissue failure isolates to its pane", async () => {
  const shop = createHelpdeskShop({
    client: createHelpdeskClient({
      async invoke(tool) {
        if (tool === "helpdesk.get_returns") return { ok: false, error: "shopify_error", message: "down" };
        throw new Error("offline");
      },
    }),
    fallback: createFixtureShop({ fail: { returns: "down" } }),
  });
  const organ = createInboxOrgan({ shop, viewId: "mine" });
  const snap = await organ.ready();
  assert.match(snap.html, /Where is my order #1001/);
  assert.match(snap.html, /Ada Demo/);
  assert.match(snap.html, /Oak Demo Rattle/);
  assert.match(snap.html, /Couldn(?:'|&#39;)t load Returns\. Retry\./);
  assert.equal(snap.rail.models.customer.ok, true);
  assert.equal(snap.rail.models.order.ok, true);
  assert.equal(snap.rail.models.returns.ok, false);
});

test("composer tools share invoke and are not writes", async () => {
  const calls = [];
  const shop = createHelpdeskShop({
    client: createHelpdeskClient({
      async invoke(tool, args) {
        calls.push([tool, args.ticketId]);
        if (tool === "helpdesk.draft_reply") return { ok: true, source: "fixture", draft: "Hi Ada — fixture draft." };
        if (tool === "helpdesk.summarize_thread") return { ok: true, source: "fixture", summary: "Ada asked about #1001." };
        return { ok: false };
      },
    }),
  });
  const draft = await shop.draftReply({ ticketId: "t-ada-track" });
  const summary = await shop.summarizeThread({ ticketId: "t-ada-track" });
  assert.equal(draft.draft, "Hi Ada — fixture draft.");
  assert.equal(summary.summary, "Ada asked about #1001.");
  assert.deepEqual(calls, [
    ["helpdesk.draft_reply", "t-ada-track"],
    ["helpdesk.summarize_thread", "t-ada-track"],
  ]);
});

test("CLI draft-reply and summarize-thread return text", () => {
  const draft = pythonInvoke("helpdesk.draft_reply", { ticketId: "1001", shop: SAMPLE_SHOP });
  assert.equal(draft.ok, true);
  assert.match(draft.draft, /Ada|#9001/);
  assert.doesNotMatch(draft.draft, /gorgias|Malky|Rivky|refund you/i);
  const summary = pythonInvoke("helpdesk.summarize_thread", { ticketId: "1001" });
  assert.equal(summary.ok, true);
  assert.match(summary.summary, /Ada/);
  assert.doesNotMatch(summary.summary, />Send</);
});

test("shop adapter has no mutation surface", async () => {
  const shop = createHelpdeskShop({
    client: createHelpdeskClient({
      async invoke(tool) {
        if (WRITE_TOOLS.includes(tool)) {
          return { ok: false, error: "forbidden", message: "Shopify writes are refused. SHOPIFY_MUTATIONS_ENABLED stays 0." };
        }
        return { ok: false };
      },
    }),
  });
  assert.equal("getCustomer" in shop, true);
  assert.equal("mutate" in shop, false);
  assert.equal("createRefund" in shop, false);
  assert.equal("cancelOrder" in shop, false);
  const payload = await shop.client.invoke("helpdesk.refund", {});
  assert.equal(payload.ok, false);
  assert.equal(payload.error, "forbidden");
  assert.match(payload.message, /SHOPIFY_MUTATIONS_ENABLED stays 0/);
});

test("resolveLiveInbox remounts only when source is live", async () => {
  const live = await resolveLiveInbox({
    invoke: async () => ({ ok: true, source: "live", customer: { id: LIVE_IDS.C_UNFULFILLED } }),
  });
  assert.equal(live.shop, LIVE_SHOP);
  assert.equal(live.tickets.length, fixtureTickets.length);
  assert.ok(live.tickets.every((ticket) => !/Ada Demo/.test(JSON.stringify(ticket))));

  const sample = await resolveLiveInbox({
    invoke: async () => ({ ok: true, source: "sample", customer: { id: LIVE_IDS.C_UNFULFILLED } }),
  });
  assert.equal(sample, null);

  const down = await resolveLiveInbox({
    invoke: async () => {
      throw new Error("no mint");
    },
  });
  assert.equal(down, null);
});

test("null SKU and missing billing stay hidden on a live-hole order", async () => {
  const shop = createHelpdeskShop({
    client: clientFromPython("live-holes"),
    shop: LIVE_SHOP,
  });
  const order = await shop.getOrder({ shop: LIVE_SHOP, orderId: LIVE_IDS.O_1002 });
  assert.equal(order.lineItems.nodes[0].sku, undefined);
  assert.equal(order.billingAddress, null);
  const html = (await import("../js/tissues/order.js")).renderOrder(projectOrder(order), { addressesOpen: true });
  assert.doesNotMatch(html, /data-sku=/);
  assert.doesNotMatch(html, />\s*null\s*</);
  assert.match(html, /No billing/);
});
