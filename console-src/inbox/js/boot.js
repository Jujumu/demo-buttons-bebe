import { createInboxOrgan } from "./inbox.js";
import { createHelpdeskClient } from "./shop/helpdesk-client.js";
import { createHelpdeskShop, resolveLiveInbox } from "./shop/helpdesk-shop.js";

const root = document.getElementById("inbox-root");
const client = createHelpdeskClient();
const shop = createHelpdeskShop({ client });
const live = await resolveLiveInbox(client);
if (live) shop.setShop(live.shop);
const organ = createInboxOrgan({
  shop,
  tickets: live?.tickets,
  shopHost: live?.shop,
});
organ.mount(root);
