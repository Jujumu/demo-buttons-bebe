import { createInboxOrgan } from "./inbox.js";
import { createHelpdeskClient } from "./shop/helpdesk-client.js";
import { createHelpdeskShop, resolveLiveInbox } from "./shop/helpdesk-shop.js";
import { registerInboxWebMcp } from "./webmcp.js";

const root = document.getElementById("inbox-root");
const client = createHelpdeskClient();
const shop = createHelpdeskShop({ client });
const live = await resolveLiveInbox(client);
if (live) shop.setShop(live.shop);
const params = new URLSearchParams(location.search);
// Always list from helpdesk.list_tickets (SEED + intake). Live mint only
// pins the shop host — do not replace the catalog with the 5-row live stub.
// Default chrome is Assigned to me. ?view=open is the Open queue.
// ?view=escalated is the Escalated queue.
// ?empty=1 pins an empty catalog so filtered empty copy can be reviewed.
const emptyList = params.get("empty") === "1";
const organ = createInboxOrgan({
  shop,
  shopHost: live?.shop,
  viewId: params.get("view") || "mine",
  ticketId: emptyList ? undefined : (params.get("ticket") || undefined),
  tickets: emptyList ? [] : undefined,
  privacyGate: params.get("gate") === "privacy",
});
if (params.get("pull") === "1") {
  const pullArgs = { limit: Number(params.get("limit") || 20) || 20 };
  if (params.get("force") === "1") pullArgs.force = true;
  await organ.pullMailbox(pullArgs);
}
await organ.mount(root);
if (params.get("menu") === "1") {
  root.querySelector("[data-list-filter]")?.click();
}

// Demo/review: expose organ for WebMCP verify + headless shots (not a product API).
globalThis.__inboxOrgan = organ;

// WebMCP: register Document-scoped chrome tools after mount. No-op without
// modelContext (chrome://flags/#enable-webmcp-testing). Abort on page hide.
const webmcp = registerInboxWebMcp(organ);
await webmcp.ready;
globalThis.__inboxWebMcp = webmcp;
window.addEventListener("pagehide", () => webmcp.dispose(), { once: true });
