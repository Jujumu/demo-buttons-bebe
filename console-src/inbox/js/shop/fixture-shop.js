import { customers, emptyReturns, orders, SHOP } from "../fixtures/demo-inbox.js";

function assertShop(shop) {
  if (shop && shop !== SHOP) {
    throw new Error("shop tissue refused an unknown fixture shop");
  }
}

function historyRow(order) {
  return {
    id: order.id,
    name: order.name,
    createdAt: order.createdAt,
    total: order.currentTotalPriceSet?.shopMoney?.amount
      ? `${order.currentTotalPriceSet.shopMoney.amount} ${order.currentTotalPriceSet.shopMoney.currencyCode}`
      : "",
    fulfillmentStatus: order.displayFulfillmentStatus,
  };
}

/**
 * Fixture shop tissue. Clerk replaces this later with a read-only Admin
 * GraphQL client. No network, no mutations.
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
        return { ...emptyReturns };
      }
      return { ...emptyReturns };
    },
    getOrderHistory({ shop, customerId }) {
      assertShop(shop);
      maybeFail("order-history");
      return Object.values(orders)
        .filter((order) => order.customerId === customerId)
        .map(historyRow)
        .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
    },
  };
}
