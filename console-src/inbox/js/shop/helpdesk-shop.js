import { tickets as fixtureTickets, SHOP as FIXTURE_SHOP } from "../fixtures/demo-inbox.js";
import { createHelpdeskClient } from "./helpdesk-client.js";
import { createFixtureShop } from "./fixture-shop.js";
import { LIVE_PROBE_CUSTOMER, LIVE_SHOP, liveTickets } from "./live-catalog.js";
import { WRITE_TOOLS } from "./helpdesk-tools.js";

function extractReturns(payload) {
  return {
    orderReturnStatus: payload.orderReturnStatus || "NO_RETURN",
    returns: payload.returns || { nodes: [] },
    inProgress: Boolean(payload.inProgress),
    items: payload.items || [],
    refundTotal: payload.refundTotal ?? null,
    creditTotal: payload.creditTotal ?? null,
    tracking: payload.tracking ?? null,
  };
}

/**
 * Shop tissue that speaks the helpdesk-agent contracts.
 * Live Cute Things when mint works. Fixture fallback otherwise.
 * Ada's invented OPEN return stays on the fixture catalog only.
 *
 * @param {{ client?: object, fallback?: object, shop?: string, fail?: Record<string, Error | string> }} [opts]
 */
export function createHelpdeskShop(opts = {}) {
  const client = opts.client || createHelpdeskClient();
  const fallback = opts.fallback || createFixtureShop({ fail: opts.fail });
  let activeShop = opts.shop || fallback.shop || FIXTURE_SHOP;

  async function read(tool, args, pick) {
    if (WRITE_TOOLS.includes(tool)) {
      throw new Error("Shopify writes are refused. SHOPIFY_MUTATIONS_ENABLED stays 0.");
    }
    try {
      const payload = await client.invoke(tool, args);
      if (payload && payload.ok) return pick(payload);
    } catch {
      // Mint/Admin/HTTP unavailable — fixture catalog is the fallback.
    }
    return undefined;
  }

  return {
    id: "shop",
    get shop() {
      return activeShop;
    },
    setShop(next) {
      if (next) activeShop = next;
      return activeShop;
    },
    client,
    async getCustomer({ shop, customerId }) {
      if (!customerId) return null;
      const record = await read(
        "helpdesk.get_customer",
        { shop: shop || activeShop, customerId },
        (payload) => payload.customer,
      );
      if (record) return record;
      return fallback.getCustomer({ shop: fallback.shop, customerId });
    },
    async getOrder({ shop, orderId }) {
      if (!orderId) return null;
      const record = await read(
        "helpdesk.get_order",
        { shop: shop || activeShop, orderId },
        (payload) => payload.order,
      );
      if (record) return record;
      return fallback.getOrder({ shop: fallback.shop, orderId });
    },
    async getReturns({ shop, orderId }) {
      const record = await read(
        "helpdesk.get_returns",
        { shop: shop || activeShop, orderId },
        extractReturns,
      );
      if (record) return record;
      return fallback.getReturns({ shop: fallback.shop, orderId });
    },
    async getOrderHistory({ shop, customerId }) {
      if (!customerId) return [];
      const rows = await read(
        "helpdesk.list_past_orders",
        { shop: shop || activeShop, customerId },
        (payload) => payload.orders,
      );
      if (rows) return rows;
      return fallback.getOrderHistory({ shop: fallback.shop, customerId });
    },
  };
}

/**
 * Use the live Cute Things ticket catalog only when mint actually succeeded.
 * Live-hole / sample fallbacks keep the invented Ada OPEN fixture inbox.
 */
export async function resolveLiveInbox(client) {
  if (!client?.invoke) return null;
  try {
    const payload = await client.invoke("helpdesk.get_customer", {
      shop: LIVE_SHOP,
      customerId: LIVE_PROBE_CUSTOMER,
    });
    if (payload?.ok && payload.source === "live") {
      return { shop: LIVE_SHOP, tickets: liveTickets, source: "live" };
    }
  } catch {
    // fixtures
  }
  return null;
}

export function fixtureInboxCatalog() {
  return { shop: FIXTURE_SHOP, tickets: fixtureTickets, source: "sample" };
}
