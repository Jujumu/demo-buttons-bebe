import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { IDS, SHOP, emptyReturns, orders } from "../js/fixtures/demo-inbox.js";
import { formatSku } from "../js/util.js";
import { createFixtureShop } from "../js/shop/fixture-shop.js";
import { projectCustomer } from "../js/tissues/customer.js";
import { projectOrderHistory } from "../js/tissues/order-history.js";
import { projectOrder, renderOrder } from "../js/tissues/order.js";
import { projectReturns, renderReturns } from "../js/tissues/returns.js";
import { createMailbox } from "../js/mailbox.js";
import { createRailOrgan } from "../js/tissues/rail.js";

const shop = createFixtureShop();
const here = dirname(fileURLToPath(import.meta.url));

function clickToggle(host, name) {
  host.onclick({
    target: {
      closest(sel) {
        if (sel === "[data-history]") return null;
        if (sel === "[data-toggle]") return { dataset: { toggle: name } };
        return null;
      },
    },
  });
}

function assertMoneyBag(bag) {
  assert.deepEqual(Object.keys(bag).sort(), ["presentmentMoney", "shopMoney"]);
  assert.equal(typeof bag.shopMoney.amount, "string");
  assert.equal(typeof bag.presentmentMoney.amount, "string");
}

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
  assert.equal(model.record.defaultEmailAddress.emailAddress, "ada.demo@example.com");
  assert.equal(model.record.email, undefined);
  assert.ok(!("email" in model.record));
  assert.deepEqual(model.record.tags, ["DEMO"]);
  assert.equal(typeof model.record.numberOfOrders, "string");
  assert.equal(model.record.numberOfOrders, "1");
});

test("order fixture keeps null SKUs and missing billing", async () => {
  const order = await shop.getOrder({ shop: SHOP, orderId: IDS.ORDER_1001 });
  assert.equal(order.lineItems.nodes[0].sku, null);
  assert.equal(order.billingAddress, null);
  const model = projectOrder(order);
  assert.equal(model.skuLabels[0], "");
  assert.equal(formatSku(order.lineItems.nodes[0].sku), "");
  assert.equal(model.addressPeek, "No billing");
  assert.match(model.peek, /#1001/);
  assert.match(model.peek, /Paid/);
  assert.match(model.peek, /Fulfilled/);
  const html = renderOrder(model, { open: true, addressesOpen: true });
  assert.doesNotMatch(html, /data-sku=/);
  assert.doesNotMatch(html, /<th>SKU<\/th>/);
  assert.doesNotMatch(html, /class="mono line-sku"/);
  assert.doesNotMatch(html, /CT-TEETHER|SKU-1001|fake-sku/i);
  assert.match(html, /No billing/);
  assert.match(html, /Absent/);
  assert.match(html, /Demo Carrier DEMO-1001/);
  assert.doesNotMatch(html, />https:\/\/example\.com\/track\/demo-1001</);
  assertMoneyBag(order.currentTotalPriceSet);
  assertMoneyBag(order.lineItems.nodes[0].originalUnitPriceSet);
  assert.equal(order.lineItems.nodes[0].originalUnitPriceSet.shopMoney.amount, "24.00");
  assert.equal(order.lineItems.nodes[0].price, undefined);
});

test("unfulfilled order has no shipment block and still null SKU", async () => {
  const order = await shop.getOrder({ shop: SHOP, orderId: IDS.ORDER_1002 });
  const model = projectOrder(order);
  assert.equal(order.lineItems.nodes[0].sku, null);
  assert.equal(model.hasTracking, false);
  const html = renderOrder(model);
  assert.doesNotMatch(html, /Shipment/);
  assert.doesNotMatch(html, /data-sku=/);
  assert.equal(model.addressPeek, "No billing");
});

test("different billing peeks Ship ≠ bill without crashing", async () => {
  const order = await shop.getOrder({ shop: SHOP, orderId: IDS.ORDER_1003 });
  assert.ok(order.billingAddress);
  const model = projectOrder(order);
  assert.equal(model.addressPeek, "Ship ≠ bill");
  assert.equal(renderOrder(model, { addressesOpen: true }).includes("4 Preview Court"), true);
});

test("matching billing peeks Same address", async () => {
  const order = await shop.getOrder({ shop: SHOP, orderId: IDS.ORDER_1003 });
  const model = projectOrder({ ...order, billingAddress: { ...order.shippingAddress } });
  assert.equal(model.addressPeek, "Same address");
});

test("a present SKU renders a mono row and a null SKU does not", () => {
  const withSku = projectOrder({
    ...orders[IDS.ORDER_1002],
    lineItems: { nodes: [{ title: "Canvas Demo Visor", sku: "DEMO-VISOR", quantity: 1, originalUnitPriceSet: orders[IDS.ORDER_1002].lineItems.nodes[0].originalUnitPriceSet }] },
  });
  assert.equal(withSku.skuLabels[0], "DEMO-VISOR");
  assert.match(renderOrder(withSku), /<p class="mono line-sku" data-sku="DEMO-VISOR">DEMO-VISOR<\/p>/);
  const hidden = projectOrder(orders[IDS.ORDER_1002]);
  assert.equal(hidden.skuLabels[0], "");
  assert.doesNotMatch(renderOrder(hidden), /line-sku|data-sku=/);
});

test("empty demo returns peek No returns and stay collapsed", async () => {
  const record = await shop.getReturns({ shop: SHOP, orderId: IDS.ORDER_1002 });
  assert.deepEqual(record.returns, emptyReturns.returns);
  assert.equal(record.returns.nodes.length, 0);
  assert.equal(record.returnStatus, undefined);
  const model = projectReturns(record);
  assert.equal(model.peek, "No returns");
  assert.equal(model.collapsedDefault, true);
  assert.equal(model.record.returns.nodes.length, 0);
  const html = renderReturns(model);
  assert.match(html, /data-open="false"/);
  assert.match(html, /No returns/);
});

test("Ada OPEN return peeks in-progress and default-opens", async () => {
  const record = await shop.getReturns({ shop: SHOP, orderId: IDS.ORDER_1001 });
  assert.equal(record.returns.nodes[0].status, "OPEN");
  assert.equal(record.returnStatus, undefined);
  assert.equal(record.items.length, 1);
  const model = projectReturns(record);
  assert.equal(model.peek, "In transit · 1 item");
  assert.equal(model.collapsedDefault, false);
  assert.equal(model.inProgress, true);
  assert.equal(model.record.status, "OPEN");
  const html = renderReturns(model);
  assert.match(html, /data-open="true"/);
  assert.match(html, /In transit · 1 item/);
  assert.doesNotMatch(html, /IN_PROGRESS/);
});

test("in-progress is Return.status OPEN only — no PENDING, ignore Order.returnStatus", () => {
  const src = readFileSync(join(here, "../js/tissues/returns.js"), "utf8");
  assert.doesNotMatch(src, /PENDING/);
  assert.equal(projectReturns({
    returnStatus: "OPEN",
    inProgress: true,
    returns: { nodes: [] },
    items: [],
  }).inProgress, false);
  assert.equal(projectReturns({
    returns: { nodes: [{ status: "REQUESTED" }] },
    items: [{ title: "Demo" }],
  }).inProgress, false);
  assert.equal(projectReturns({
    returns: { nodes: [{ status: "CLOSED" }] },
    items: [{ title: "Demo" }],
  }).inProgress, false);
  assert.equal(projectReturns({
    returns: { nodes: [{ status: "OPEN" }] },
    items: [{ title: "Demo" }],
  }).inProgress, true);
});

test("click closes OPEN returns and the user toggle wins", async () => {
  const rail = createRailOrgan({ shop, mailbox: createMailbox() });
  await rail.load({ shop: SHOP, customerId: IDS.ADA, orderId: IDS.ORDER_1001, ticketId: "t-ada-track" });
  assert.equal(rail.snapshot().open.returns, true);
  const host = { innerHTML: "", onclick: null };
  rail.mount(host);
  assert.match(host.innerHTML, /data-tissue="returns"[^>]*data-open="true"/);
  clickToggle(host, "returns");
  assert.equal(rail.snapshot().open.returns, false);
  assert.match(host.innerHTML, /data-tissue="returns"[^>]*data-open="false"/);
  await rail.load({ shop: SHOP, customerId: IDS.ADA, orderId: IDS.ORDER_1001, ticketId: "t-ada-track" });
  assert.equal(rail.snapshot().open.returns, false, "same ticket must not re-force OPEN");
});

test("switching tickets resets expand to lock defaults", async () => {
  const rail = createRailOrgan({ shop, mailbox: createMailbox() });
  await rail.load({ shop: SHOP, customerId: IDS.ADA, orderId: IDS.ORDER_1001, ticketId: "t-ada-track" });
  const host = { innerHTML: "", onclick: null };
  rail.mount(host);
  clickToggle(host, "returns");
  clickToggle(host, "order-history");
  clickToggle(host, "customer");
  assert.equal(rail.snapshot().open.returns, false);
  assert.equal(rail.snapshot().open["order-history"], true);
  assert.equal(rail.snapshot().open.customer, false);

  await rail.load({ shop: SHOP, customerId: IDS.CASEY, orderId: IDS.ORDER_1002, ticketId: "t-casey-visor" });
  const casey = rail.snapshot().open;
  assert.equal(casey.customer, true);
  assert.equal(casey.order, true);
  assert.equal(casey.returns, false);
  assert.equal(casey["order-history"], false);
  assert.equal(casey.addresses, false);

  await rail.load({ shop: SHOP, customerId: IDS.JORDAN, orderId: null, ticketId: "t-jordan-ship" });
  assert.equal(rail.snapshot().open.returns, false);

  await rail.load({ shop: SHOP, customerId: IDS.ADA, orderId: IDS.ORDER_1001, ticketId: "t-ada-track" });
  assert.equal(rail.snapshot().open.returns, true);
  assert.equal(rail.snapshot().open["order-history"], false);
  assert.equal(rail.snapshot().open.customer, true);
});

test("order-history is newest first and does not replace This order", async () => {
  const rows = await shop.getOrderHistory({ shop: SHOP, customerId: IDS.CASEY });
  const model = projectOrderHistory(rows);
  assert.deepEqual(model.rows.map((row) => row.name), ["#1003", "#1002"]);
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
  await rail.load({ shop: SHOP, customerId: IDS.CASEY, orderId: IDS.ORDER_1002 });
  assert.equal(rail.snapshot().currentOrderId, IDS.ORDER_1002);
  assert.equal(rail.snapshot().models.order.record.name, "#1002");

  const host = {
    innerHTML: "",
    onclick: null,
  };
  rail.mount(host);
  const before = rail.snapshot().models.order.record.name;
  host.onclick({
    target: {
      closest(sel) {
        if (sel === "[data-history]") return { dataset: { history: IDS.ORDER_1003 } };
        return null;
      },
    },
  });
  assert.equal(rail.snapshot().models.order.record.name, before);
  assert.equal(rail.snapshot().peekedHistoryId, IDS.ORDER_1003);
  assert.equal(peeks[0].orderId, IDS.ORDER_1003);
});

test("shop tissue has no mutation surface", () => {
  assert.equal("getCustomer" in shop && "getOrder" in shop, true);
  assert.equal("mutate" in shop, false);
  assert.equal("createRefund" in shop, false);
  assert.equal("cancelOrder" in shop, false);
  assert.equal(orders[IDS.ORDER_1001].lineItems.nodes[0].sku, null);
});
