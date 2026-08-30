import { createInboxOrgan } from "./inbox.js";
import { createHelpdeskClient } from "./shop/helpdesk-client.js";
import { createHelpdeskShop, resolveLiveInbox } from "./shop/helpdesk-shop.js";

const root = document.getElementById("inbox-root");
const client = createHelpdeskClient();
const shop = createHelpdeskShop({ client });
const live = await resolveLiveInbox(client);
if (live) shop.setShop(live.shop);
const params = new URLSearchParams(location.search);
const organ = createInboxOrgan({
  shop,
  tickets: live?.tickets,
  shopHost: live?.shop,
  viewId: params.get("view") || undefined,
  ticketId: params.get("ticket") || undefined,
});
organ.mount(root);
