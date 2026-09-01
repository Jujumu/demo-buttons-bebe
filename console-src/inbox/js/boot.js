import { createInboxOrgan } from "./inbox.js";
import { createHelpdeskClient } from "./shop/helpdesk-client.js";
import { createHelpdeskShop, resolveLiveInbox } from "./shop/helpdesk-shop.js";

const root = document.getElementById("inbox-root");
const client = createHelpdeskClient();
const shop = createHelpdeskShop({ client });
const live = await resolveLiveInbox(client);
if (live) shop.setShop(live.shop);
const params = new URLSearchParams(location.search);
// Always list from helpdesk.list_tickets (SEED + intake). Live mint only
// pins the shop host — do not replace the catalog with the 5-row live stub.
const organ = createInboxOrgan({
  shop,
  shopHost: live?.shop,
  viewId: params.get("view") || "open",
  ticketId: params.get("ticket") || undefined,
});
if (params.get("pull") === "1") {
  const pullArgs = { limit: Number(params.get("limit") || 20) || 20 };
  if (params.get("force") === "1") pullArgs.force = true;
  await organ.pullMailbox(pullArgs);
}
organ.mount(root);
