import { TOOL_NAMES } from "./helpdesk-tools.js";

export const HELPDESK_HTTP_PATH = "/console/api/helpdesk";

/**
 * Browser/Node client for the eight helpdesk.* tools.
 * Same payloads as MCP and CLI. No GraphQL here.
 *
 * @param {{ invoke?: Function, url?: string, fetch?: typeof fetch }} [opts]
 */
export function createHelpdeskClient(opts = {}) {
  const url = opts.url || HELPDESK_HTTP_PATH;
  const fetchImpl = opts.fetch || globalThis.fetch;
  const custom = opts.invoke;

  async function invoke(tool, args = {}) {
    if (custom) return custom(tool, args);
    if (typeof fetchImpl !== "function") {
      throw new Error("helpdesk client has no fetch");
    }
    const response = await fetchImpl(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ tool, arguments: args || {} }),
    });
    const payload = await response.json();
    if (!payload || typeof payload !== "object") {
      throw new Error("helpdesk client received an empty payload");
    }
    return payload;
  }

  return {
    id: "helpdesk-client",
    tools: TOOL_NAMES,
    invoke,
    listTickets(args) {
      return invoke("helpdesk.list_tickets", args);
    },
    getTicket(args) {
      return invoke("helpdesk.get_ticket", args);
    },
    getCustomer(args) {
      return invoke("helpdesk.get_customer", args);
    },
    getOrder(args) {
      return invoke("helpdesk.get_order", args);
    },
    getReturns(args) {
      return invoke("helpdesk.get_returns", args);
    },
    listPastOrders(args) {
      return invoke("helpdesk.list_past_orders", args);
    },
    draftReply(args) {
      return invoke("helpdesk.draft_reply", args);
    },
    summarizeThread(args) {
      return invoke("helpdesk.summarize_thread", args);
    },
  };
}
