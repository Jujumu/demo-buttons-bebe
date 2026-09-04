# Inbox lock

Four panes only: views **200** / list **300** / thread **flex** / rail **300**.
Selected list row is a **4px `#1C1916` ink bar**. No grey wash. IBM Plex.
Palette: ground `#F4F0EA`, surface `#FFFDF9`, ink `#1C1916`, mute `#5C564F`,
accent `#B5471D`. Human Send only. No Gorgias chrome, purple, Gaia, or a
fifth AI column. No Customer Edit, Refund, or Cancel.

Empty-copy voice is short and parallel:

- No billing
- No returns
- No tracking
- No customer on this ticket

## This order — fulfillment + partial ship

The rail is a client of `helpdesk.get_order` (same `dispatch()` / `invoke()`
path as MCP + CLI). No second data path. Do not invent tracking.

1. **Unfulfilled / empty shipment** — peek `No tracking`. Shipment stays
   collapsed. Ada-style `#1001` / empty `fulfillments` is this state.
2. **Fulfilled / in transit** — when `fulfillments[].trackingInfo` has a
   number or URL, open Shipment. Show **company name** + **tracking number**
   as copy (number in IBM Plex Mono). A separate **Track** control opens the
   carrier URL when `url` is present. Do not merge carrier + number into one
   accent link. `Fulfillment.displayStatus` (e.g. `IN_TRANSIT`) may peek
   **In transit**. Accent stays on Track only.
3. **Partially fulfilled** — `Order.displayFulfillmentStatus` is
   `PARTIALLY_FULFILLED`. Each line shows an official
   `LineItem.unfulfilledQuantity` cue so some lines read **Shipped** and
   the rest **Unfulfilled** (or `N of Q unfulfilled`). Shopkeep can answer
   “where’s the rest?” without leaving the inbox.

Miss → `No tracking` / unfulfilled line cue. Never invent a tracking number.
Title-case on screen (`Unfulfilled`, `Partially Fulfilled`, `In transit`).
Enums in data stay Shopify (`UNFULFILLED`, `PARTIALLY_FULFILLED`, `IN_TRANSIT`).
