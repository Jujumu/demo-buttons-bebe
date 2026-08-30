/** Locked v1 tool names. Same ten as MCP/CLI. No send/refund/cancel. */
export const TOOL_NAMES = Object.freeze([
  "helpdesk.list_tickets",
  "helpdesk.get_ticket",
  "helpdesk.get_customer",
  "helpdesk.get_order",
  "helpdesk.get_returns",
  "helpdesk.list_past_orders",
  "helpdesk.draft_reply",
  "helpdesk.summarize_thread",
  "helpdesk.search_macros",
  "helpdesk.apply_macro",
]);

export const WRITE_TOOLS = Object.freeze([
  "helpdesk.send",
  "helpdesk.refund",
  "helpdesk.cancel",
]);

export const RAIL_TOOLS = Object.freeze({
  customer: "helpdesk.get_customer",
  order: "helpdesk.get_order",
  returns: "helpdesk.get_returns",
  history: "helpdesk.list_past_orders",
});

export const COMPOSER_TOOLS = Object.freeze({
  draft: "helpdesk.draft_reply",
  summarize: "helpdesk.summarize_thread",
  searchMacros: "helpdesk.search_macros",
  applyMacro: "helpdesk.apply_macro",
});
