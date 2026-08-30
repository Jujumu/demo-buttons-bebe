import { customers, emptyReturns, orders, returnsForOrder, SHOP } from "../fixtures/demo-inbox.js";

function assertShop(shop) {
  if (shop && shop !== SHOP) {
    throw new Error("shop tissue refused an unknown fixture shop");
  }
}

function historyRow(order) {
  const shopMoney = order.currentTotalPriceSet?.shopMoney;
  return {
    id: order.id,
    name: order.name,
    createdAt: order.createdAt,
    displayFulfillmentStatus: order.displayFulfillmentStatus,
    currentTotalPriceSet: shopMoney ? { shopMoney: { ...shopMoney } } : { shopMoney: { amount: "0.00", currencyCode: "USD" } },
  };
}

/**
 * Fixture shop tissue. Fallback when helpdesk mint/Admin is unavailable.
 * Same Clerk DTO shapes as helpdesk.get_customer / get_order / get_returns /
 * list_past_orders. No network, no mutations.
 *
 * @param {{ fail?: Record<string, Error | string> }} [opts]
 */
export function createFixtureShop(opts = {}) {
  const fail = opts.fail || {};

  function maybeFail(key) {
    if (!fail[key]) return;
    throw fail[key] instanceof Error ? fail[key] : new Error(String(fail[key]));
  }

  return {
    id: "shop",
    shop: SHOP,
    getCustomer({ shop, customerId }) {
      assertShop(shop);
      maybeFail("customer");
      return customers[customerId] || null;
    },
    getOrder({ shop, orderId }) {
      assertShop(shop);
      maybeFail("order");
      if (!orderId) return null;
      return orders[orderId] || null;
    },
    getReturns({ shop, orderId }) {
      assertShop(shop);
      maybeFail("returns");
      if (!orderId || !orders[orderId]) {
        return { ...emptyReturns, returns: { nodes: [] }, items: [] };
      }
      return returnsForOrder(orderId);
    },
    getOrderHistory({ shop, customerId }) {
      assertShop(shop);
      maybeFail("order-history");
      return Object.values(orders)
        .filter((order) => order.customerId === customerId)
        .map(historyRow)
        .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
    },
    draftReply(args = {}) {
      maybeFail("draft");
      const thread = args.thread || {};
      return {
        source: "sample",
        draft: thread.stubDraft || "",
      };
    },
    summarizeThread(args = {}) {
      maybeFail("summarize");
      const thread = args.thread || {};
      return {
        source: "sample",
        summary: thread.stubSummary || "",
      };
    },
  };
}
