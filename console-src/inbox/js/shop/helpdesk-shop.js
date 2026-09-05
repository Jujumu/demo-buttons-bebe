import { tickets as fixtureTickets, SHOP as FIXTURE_SHOP, customers as fixtureCustomers, orders as fixtureOrders } from "../fixtures/demo-inbox.js";
import { createHelpdeskClient } from "./helpdesk-client.js";
import { createFixtureShop } from "./fixture-shop.js";
import { LIVE_IDS, LIVE_PROBE_CUSTOMER, LIVE_SHOP, liveTickets } from "./live-catalog.js";
import { WRITE_TOOLS } from "./helpdesk-tools.js";

const LIVE_GID_SET = new Set(Object.values(LIVE_IDS));

/** Python sample / SEED GIDs (fixtures_sample). Must not hit Cute Things. */
const SAMPLE_GIDS = Object.freeze([
  "gid://shopify/Customer/9001",
  "gid://shopify/Customer/9002",
  "gid://shopify/Customer/9003",
  "gid://shopify/Customer/9004",
  "gid://shopify/Order/9001",
  "gid://shopify/Order/9002",
  "gid://shopify/Order/9003",
  "gid://shopify/Order/9004",
  "gid://shopify/GiftCard/9001",
  "gid://shopify/Return/90011",
]);
const SAMPLE_GID_SET = new Set(SAMPLE_GIDS);

/**
 * Offline JS fixture keys historically used 90001 / 80001.
 * Helpdesk SEED returns sample 9001 / 9001 — alias so fixture fallback joins.
 */
const FIXTURE_ID_ALIASES = Object.freeze({
  "gid://shopify/Customer/9001": "gid://shopify/Customer/90001",
  "gid://shopify/Customer/9002": "gid://shopify/Customer/90002",
  "gid://shopify/Customer/9003": "gid://shopify/Customer/90003",
  "gid://shopify/Order/9001": "gid://shopify/Order/80001",
  "gid://shopify/Order/9002": "gid://shopify/Order/80002",
  "gid://shopify/Order/9003": "gid://shopify/Order/80003",
});

function fixtureId(gid) {
  return FIXTURE_ID_ALIASES[gid] || gid;
}

function isSampleGid(gid) {
  if (!gid) return false;
  if (SAMPLE_GID_SET.has(gid)) return true;
  if (FIXTURE_ID_ALIASES[gid]) return true;
  if (Object.values(FIXTURE_ID_ALIASES).includes(gid)) return true;
  if (fixtureCustomers?.[gid] || fixtureOrders?.[gid]) return true;
  return false;
}

/**
 * Route GIDs to the shop that can actually load them.
 * Live Cute Things GIDs → live shop. Sample/SEED GIDs → fixture shop.
 * Never send sample 9001.* to yznyc1-ez (not_found → empty rail / bad draft).
 */
function shopForGid(shop, gid) {
  if (gid && LIVE_GID_SET.has(gid)) return LIVE_SHOP;
  if (isSampleGid(gid)) return FIXTURE_SHOP;
  return shop || FIXTURE_SHOP;
}

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
        { shop: shopForGid(shop || activeShop, customerId), customerId },
        (payload) => payload.customer,
      );
      if (record) return record;
      return fallback.getCustomer({ shop: fallback.shop, customerId: fixtureId(customerId) });
    },
    async getOrder({ shop, orderId }) {
      if (!orderId) return null;
      const record = await read(
        "helpdesk.get_order",
        { shop: shopForGid(shop || activeShop, orderId), orderId },
        (payload) => payload.order,
      );
      if (record) return record;
      return fallback.getOrder({ shop: fallback.shop, orderId: fixtureId(orderId) });
    },
    async getReturns({ shop, orderId }) {
      const record = await read(
        "helpdesk.get_returns",
        { shop: shopForGid(shop || activeShop, orderId), orderId },
        extractReturns,
      );
      if (record) return record;
      return fallback.getReturns({ shop: fallback.shop, orderId: orderId ? fixtureId(orderId) : orderId });
    },
    async getOrderHistory({ shop, customerId }) {
      if (!customerId) return [];
      const rows = await read(
        "helpdesk.list_past_orders",
        { shop: shopForGid(shop || activeShop, customerId), customerId },
        (payload) => payload.orders,
      );
      if (rows) return rows;
      return fallback.getOrderHistory({ shop: fallback.shop, customerId: fixtureId(customerId) });
    },
    async draftReply(args = {}) {
      const thread = args.thread || {};
      const orderId = args.orderId || thread.orderId || null;
      const customerId = args.customerId || thread.customerId || null;
      const shop = shopForGid(args.shop || activeShop, orderId || customerId);
      const record = await read(
        "helpdesk.draft_reply",
        { ...args, shop, customerId, orderId },
        (payload) => ({ draft: payload.draft || "", source: payload.source || "live" }),
      );
      // Hollow "once an order…" drafts are not ok when a join GID is present — fall through.
      const hollow =
        orderId
        && record?.draft
        && /once an order is on this ticket/i.test(record.draft);
      if (record?.draft && !hollow) return record;
      return fallback.draftReply({
        ...args,
        shop: fallback.shop,
        customerId: customerId ? fixtureId(customerId) : customerId,
        orderId: orderId ? fixtureId(orderId) : orderId,
        thread: thread.id
          ? {
            ...thread,
            customerId: thread.customerId ? fixtureId(thread.customerId) : thread.customerId,
            orderId: thread.orderId ? fixtureId(thread.orderId) : thread.orderId,
          }
          : thread,
      });
    },
    async summarizeThread(args = {}) {
      const record = await read(
        "helpdesk.summarize_thread",
        { ...args, shop: args.shop || activeShop },
        (payload) => ({ summary: payload.summary || "", source: payload.source || "live" }),
      );
      if (record?.summary) return record;
      return fallback.summarizeThread(args);
    },
    async searchMacros(args = {}) {
      const record = await read(
        "helpdesk.search_macros",
        { query: args.query || "" },
        (payload) => ({ macros: payload.macros || [], source: payload.source || "live" }),
      );
      if (record?.macros) return record;
      return fallback.searchMacros(args);
    },
    async applyMacro(args = {}) {
      const record = await read(
        "helpdesk.apply_macro",
        {
          macroId: args.macroId,
          mode: args.mode || "replace",
          currentBody: args.currentBody || "",
        },
        (payload) => ({
          text: payload.text || "",
          title: payload.title || "",
          mode: payload.mode || "replace",
          body: payload.body || "",
          macroId: payload.macroId,
          source: payload.source || "live",
        }),
      );
      if (record?.text) return record;
      return fallback.applyMacro(args);
    },
    async listTickets({ view, limit } = {}) {
      const rows = await read(
        "helpdesk.list_tickets",
        { view: view || "open", limit: limit || 20 },
        (payload) => payload.tickets,
      );
      if (Array.isArray(rows)) return rows;
      return fallback.listTickets({ view, limit });
    },
    async getTicket({ ticketId } = {}) {
      if (!ticketId) return null;
      const record = await read(
        "helpdesk.get_ticket",
        { ticketId },
        (payload) => payload.ticket,
      );
      if (record) return record;
      return fallback.getTicket({ ticketId });
    },
    async ingestEmail(args = {}) {
      const record = await read(
        "helpdesk.ingest_email",
        args,
        (payload) => payload,
      );
      if (record) return record;
      return { ok: false, spam: false, ticketId: null };
    },
    async ingestChat(args = {}) {
      const record = await read(
        "helpdesk.ingest_chat",
        args,
        (payload) => payload,
      );
      if (record) return record;
      return { ok: false, spam: false, ticketId: null };
    },
    async pullMailbox(args = {}) {
      const record = await read(
        "helpdesk.pull_mailbox",
        { limit: args.limit || 20 },
        (payload) => payload,
      );
      if (record) return record;
      return { ok: false, ingested: [], spam: [], skipped: 0 };
    },
    async escalateTicket(args = {}) {
      const record = await read(
        "helpdesk.escalate_ticket",
        { ticketId: args.ticketId, reason: args.reason },
        (payload) => payload.ticket,
      );
      if (record) return record;
      return fallback.escalateTicket(args);
    },
    async markPrivacyHandled(args = {}) {
      // First-party flag only. No MCP write tool — never a Shopify privacy mutation.
      return fallback.markPrivacyHandled(args);
    },
    async markUnsubscribed(args = {}) {
      // First-party flag only. No MCP write tool — never a Shopify marketing mutation.
      return fallback.markUnsubscribed(args);
    },
    async markBugHandled(args = {}) {
      // First-party flag only. No MCP write tool — never a Shopify product mutation.
      return fallback.markBugHandled(args);
    },
    async writeGateStatus(args = {}) {
      const record = await read(
        "helpdesk.write_gate_status",
        args,
        (payload) => ({
          mutationsEnabled: Boolean(payload.mutationsEnabled),
          refused: payload.refused || ["send", "refund", "cancel"],
          tools: payload.tools || WRITE_TOOLS,
          message: payload.message || "Shopify writes are refused. SHOPIFY_MUTATIONS_ENABLED stays 0.",
        }),
      );
      if (record) return record;
      return fallback.writeGateStatus(args);
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

/** Test/helper export: sample GIDs must resolve to the fixture shop. */
export { shopForGid, fixtureId, SAMPLE_GIDS };
