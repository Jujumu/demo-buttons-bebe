import { tickets as fixtureTickets, SHOP as FIXTURE_SHOP } from "../fixtures/demo-inbox.js";
import { createHelpdeskClient } from "./helpdesk-client.js";
import { createFixtureShop } from "./fixture-shop.js";
import { LIVE_IDS, LIVE_PROBE_CUSTOMER, LIVE_SHOP, liveTickets } from "./live-catalog.js";
import { WRITE_TOOLS } from "./helpdesk-tools.js";

const LIVE_GID_SET = new Set(Object.values(LIVE_IDS));

function shopForGid(shop, gid) {
  if (gid && LIVE_GID_SET.has(gid)) return LIVE_SHOP;
  return shop;
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
      return fallback.getCustomer({ shop: fallback.shop, customerId });
    },
    async getOrder({ shop, orderId }) {
      if (!orderId) return null;
      const record = await read(
        "helpdesk.get_order",
        { shop: shopForGid(shop || activeShop, orderId), orderId },
        (payload) => payload.order,
      );
      if (record) return record;
      return fallback.getOrder({ shop: fallback.shop, orderId });
    },
    async getReturns({ shop, orderId }) {
      const record = await read(
        "helpdesk.get_returns",
        { shop: shopForGid(shop || activeShop, orderId), orderId },
        extractReturns,
      );
      if (record) return record;
      return fallback.getReturns({ shop: fallback.shop, orderId });
    },
    async getOrderHistory({ shop, customerId }) {
      if (!customerId) return [];
      const rows = await read(
        "helpdesk.list_past_orders",
        { shop: shopForGid(shop || activeShop, customerId), customerId },
        (payload) => payload.orders,
      );
      if (rows) return rows;
      return fallback.getOrderHistory({ shop: fallback.shop, customerId });
    },
    async draftReply(args = {}) {
      const record = await read(
        "helpdesk.draft_reply",
        { ...args, shop: args.shop || activeShop },
        (payload) => ({ draft: payload.draft || "", source: payload.source || "live" }),
      );
      if (record?.draft) return record;
      return fallback.draftReply(args);
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
