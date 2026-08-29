import assert from "node:assert/strict";
import test from "node:test";

import { IDS, SHOP, emptyReturns, orders } from "../js/fixtures/cute-things.js";
import { createFixtureShop } from "../js/shop/fixture-shop.js";
import { projectCustomer } from "../js/tissues/customer.js";
import { projectOrderHistory } from "../js/tissues/order-history.js";
import { projectOrder, renderOrder } from "../js/tissues/order.js";
import { projectReturns, renderReturns } from "../js/tissues/returns.js";
import { createMailbox } from "../js/mailbox.js";
import { createRailOrgan } from "../js/tissues/rail.js";

const shop = createFixtureShop();

test("customer DTO uses Clerk Admin GraphQL field names", async () => {
  const record = await shop.getCustomer({ shop: SHOP, customerId: IDS.ADA });
  const model = projectCustomer(record);
  assert.equal(model.ok, true);
  assert.equal(model.peek, "Ada Demo");
  assert.deepEqual(Object.keys(model.record).sort(), [
    "amountSpent",
    "createdAt",
    "defaultEmailAddress",
    "displayName",
    "numberOfOrders",
    "tags",
  ]);
  assert.equal(model.record.defaultEmailAddress.emailAddress, "ai-demo-fulfilled@example.com");
  assert.equal(model.record.email, undefined);
  assert.ok(!("email" in model.record));
  assert.deepEqual(model.record.tags, ["AI-DEMO"]);
});

test("order fixture keeps null SKUs and missing billing", async () => {
  const order = await shop.getOrder({ shop: SHOP, orderId: IDS.ORDER_1002 });
  assert.equal(order.lineItems.nodes[0].sku, null);
  assert.equal(order.billingAddress, null);
  const model = projectOrder(order);
  assert.equal(model.skuLabels[0], "—");
  assert.equal(model.addressPeek, "Ship ≠ bill");
  assert.match(model.peek, /#1002/);
  assert.match(model.peek, /Paid/);
  assert.match(model.peek, /Fulfilled/);
  const html = renderOrder(model, { open: true, addressesOpen: true });
  assert.match(html, /—/);
  assert.doesNotMatch(html, /CT-TEETHER|SKU-1002|fake-sku/i);
  assert.match(html, /Absent/);
  assert.match(html, /Demo Carrier AI-DEMO-1002/);
  assert.doesNotMatch(html, />https:\/\/example\.com\/ai-demo\/1002</);
});

test("unfulfilled order has no shipment block and still null SKU", async () => {
  const order = await shop.getOrder({ shop: SHOP, orderId: IDS.ORDER_1003 });
  const model = projectOrder(order);
  assert.equal(order.lineItems.nodes[0].sku, null);
  assert.equal(model.hasTracking, false);
  const html = renderOrder(model);
  assert.doesNotMatch(html, /Shipment/);
  assert.match(html, /No SKU|—/);
});

test("different billing peeks Ship ≠ bill without crashing", async () => {
  const order = await shop.getOrder({ shop: SHOP, orderId: IDS.ORDER_1004 });
  assert.ok(order.billingAddress);
  const model = projectOrder(order);
  assert.equal(model.addressPeek, "Ship ≠ bill");
  assert.equal(renderOrder(model, { addressesOpen: true }).includes("4 Preview Court"), true);
});

test("empty Cute Things returns peek No returns and stay collapsed", async () => {
  const record = await shop.getReturns({ shop: SHOP, orderId: IDS.ORDER_1002 });
  assert.deepEqual(record.returns, emptyReturns.returns);
  assert.equal(record.returnStatus, null);
  assert.equal(record.inProgress, false);
  const model = projectReturns(record);
  assert.equal(model.peek, "No returns");
  assert.equal(model.collapsedDefault, true);
  assert.equal(model.record.returns.nodes.length, 0);
  const html = renderReturns(model);
  assert.match(html, /data-open="false"/);
  assert.match(html, /No returns/);
});

test("order-history is newest first and does not replace This order", async () => {
  const rows = await shop.getOrderHistory({ shop: SHOP, customerId: IDS.CASEY });
  const model = projectOrderHistory(rows);
  assert.deepEqual(model.rows.map((row) => row.name), ["#1004", "#1003"]);
  assert.deepEqual(Object.keys(model.rows[0]).sort(), [
    "createdAt",
    "fulfillmentStatus",
    "id",
    "name",
    "total",
  ]);

  const mailbox = createMailbox();
  const peeks = [];
  mailbox.subscribe("history/peek", (payload) => peeks.push(payload));
  const rail = createRailOrgan({ shop, mailbox });
  await rail.load({ shop: SHOP, customerId: IDS.CASEY, orderId: IDS.ORDER_1003 });
  assert.equal(rail.snapshot().currentOrderId, IDS.ORDER_1003);
  assert.equal(rail.snapshot().models.order.record.name, "#1003");

  const host = {
    innerHTML: "",
    onclick: null,
  };
  const clicks = [];
  host.onclick = null;
  rail.mount(host);
  const before = rail.snapshot().models.order.record.name;
  host.onclick({
    target: {
      closest(sel) {
        clicks.push(sel);
        if (sel === "[data-history]") return { dataset: { history: IDS.ORDER_1004 } };
        return null;
      },
    },
  });
  assert.equal(rail.snapshot().models.order.record.name, before);
  assert.equal(rail.snapshot().peekedHistoryId, IDS.ORDER_1004);
  assert.equal(peeks[0].orderId, IDS.ORDER_1004);
});

test("shop tissue has no mutation surface", () => {
  assert.equal("getCustomer" in shop && "getOrder" in shop, true);
  assert.equal("mutate" in shop, false);
  assert.equal("createRefund" in shop, false);
  assert.equal("cancelOrder" in shop, false);
  assert.equal(orders[IDS.ORDER_1002].lineItems.nodes[0].sku, null);
});
