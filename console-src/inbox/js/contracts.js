/**
 * Inbox tissue contracts. Tissues are replaceable black boxes.
 * Other tissues know only these inputs and outputs — never internals.
 *
 * Field names on Clerk rail DTOs are locked to Shopify Admin GraphQL 2026-07
 * (read-only). The shop tissue is the only place those records are fetched.
 * This module is documentation-as-code; it exports no runtime behavior.
 */

/**
 * @typedef {object} MoneyV2
 * @property {string} amount
 * @property {string} currencyCode
 */

/**
 * @typedef {object} MoneyBag
 * @property {MoneyV2} shopMoney
 * @property {MoneyV2} presentmentMoney
 */

/**
 * @typedef {object} ClerkCustomer
 * @property {string} displayName
 * @property {{ emailAddress: string } | null} defaultEmailAddress
 * @property {string} createdAt
 * @property {string} numberOfOrders
 * @property {MoneyV2} amountSpent
 * @property {string[]} tags
 */

/**
 * @typedef {object} ClerkLineItem
 * @property {string} title
 * @property {string | null} sku
 * @property {number} quantity
 * @property {MoneyBag} originalUnitPriceSet
 */

/**
 * @typedef {object} ClerkAddress
 * @property {string | null} [name]
 * @property {string | null} [address1]
 * @property {string | null} [address2]
 * @property {string | null} [city]
 * @property {string | null} [province]
 * @property {string | null} [zip]
 * @property {string | null} [country]
 */

/**
 * @typedef {object} ClerkTrackingInfo
 * @property {string} number
 * @property {string} url
 * @property {string} company
 */

/**
 * @typedef {object} ClerkOrder
 * @property {string} id
 * @property {string} name
 * @property {string} createdAt
 * @property {string} displayFinancialStatus
 * @property {string} displayFulfillmentStatus
 * @property {MoneyBag} currentTotalPriceSet
 * @property {{ nodes: ClerkLineItem[] }} lineItems
 * @property {ClerkAddress | null} shippingAddress
 * @property {ClerkAddress | null} billingAddress
 * @property {{ trackingInfo: ClerkTrackingInfo[] }[]} fulfillments
 * @property {MoneyBag | null} [currentSubtotalPriceSet]
 * @property {MoneyBag | null} [totalShippingPriceSet]
 * @property {MoneyBag | null} [totalTaxSet]
 */

/**
 * @typedef {object} ClerkReturnItem
 * @property {string} title
 * @property {string | null} reason
 * @property {string | null} type
 */

/**
 * @typedef {object} ClerkReturn
 * @property {string} id
 * @property {string} status
 */

/**
 * @typedef {object} ClerkReturns
 * @property {{ nodes: ClerkReturn[] }} returns
 * @property {ClerkReturnItem[]} items
 * @property {MoneyBag | null} refundTotal
 * @property {MoneyBag | null} creditTotal
 * @property {ClerkTrackingInfo | null} tracking
 */

/**
 * @typedef {object} ClerkOrderHistoryRow
 * @property {string} id
 * @property {string} name
 * @property {string} createdAt
 * @property {string} displayFulfillmentStatus
 * @property {{ shopMoney: MoneyV2 }} currentTotalPriceSet
 */

/**
 * Shop tissue. The inbox rail is a client of helpdesk.* tools
 * (`get_customer`, `get_order`, `get_returns`, `list_past_orders`) via
 * `createHelpdeskShop`. Composer is a client of `draft_reply` and
 * `summarize_thread` on the same invoke(). Fixtures are the fallback when
 * mint/Admin is down. In: `{ shop, customerId?, orderId? }` plus composer
 * `{ ticketId, thread? }`. Out: the Clerk DTOs above, or `{ draft }` /
 * `{ summary }`. Must not mutate Shopify. `SHOPIFY_MUTATIONS_ENABLED` stays 0.
 *
 * @typedef {object} ShopTissue
 * @property {(req: { shop: string, customerId: string }) => Promise<ClerkCustomer | null> | ClerkCustomer | null} getCustomer
 * @property {(req: { shop: string, orderId: string }) => Promise<ClerkOrder | null> | ClerkOrder | null} getOrder
 * @property {(req: { shop: string, orderId: string }) => Promise<ClerkReturns> | ClerkReturns} getReturns
 * @property {(req: { shop: string, customerId: string }) => Promise<ClerkOrderHistoryRow[]> | ClerkOrderHistoryRow[]} getOrderHistory
 */

/**
 * Mailbox topics. Tissues publish and subscribe; they do not import each other.
 *
 * `view/selected`        { viewId }
 * `list/selected`        { ticketId }
 * `composer/body`        { text }
 * `composer/insert`      { text }
 * `composer/discard`
 * `composer/send`        { text, close: boolean }
 * `composer/summarize`   { ticketId }
 * `history/peek`         { orderId }  — does not replace This order
 * `tissue/error`         { tissueId, message }
 */

export const MAILBOX_TOPICS = Object.freeze({
  VIEW_SELECTED: "view/selected",
  LIST_SELECTED: "list/selected",
  COMPOSER_BODY: "composer/body",
  COMPOSER_INSERT: "composer/insert",
  COMPOSER_DISCARD: "composer/discard",
  COMPOSER_SEND: "composer/send",
  COMPOSER_SUMMARIZE: "composer/summarize",
  HISTORY_PEEK: "history/peek",
  TISSUE_ERROR: "tissue/error",
});

export const FORBIDDEN_CONTROLS = Object.freeze([
  "gaia",
  "refund",
  "cancel",
  "edit",
  "edit order",
  "edit-order",
  "duplicate",
  "create order",
  "customerupdate",
]);
