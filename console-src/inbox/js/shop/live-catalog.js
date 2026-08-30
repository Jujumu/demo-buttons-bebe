/**
 * Cute Things live catalog for the inbox rail when mint succeeds.
 * IDs match helpdesk fixtures_live_holes / the live shop.
 * Empty returns. No invented OPEN return.
 */

export const LIVE_SHOP = "yznyc1-ez.myshopify.com";

export const LIVE_IDS = Object.freeze({
  C_UNFULFILLED: "gid://shopify/Customer/10207427887277",
  C_FULFILLED: "gid://shopify/Customer/10207427920045",
  C_MULTI: "gid://shopify/Customer/10207427952813",
  O_1001: "gid://shopify/Order/7131035795629",
  O_1002: "gid://shopify/Order/7131035861165",
  O_1003: "gid://shopify/Order/7131035893933",
  O_1004: "gid://shopify/Order/7131035992237",
});

export const LIVE_PROBE_CUSTOMER = LIVE_IDS.C_UNFULFILLED;

const STORE_NAME = "Demo Shop";

function ticket({
  id,
  subject,
  status,
  view,
  assignee,
  customerId,
  orderId,
  updatedAt,
  stubDraft,
  stubSummary,
  messages,
}) {
  return {
    id,
    subject,
    status,
    view,
    assignee,
    customerId,
    orderId,
    updatedAt,
    stubDraft,
    stubSummary,
    messages,
  };
}

/** Same five-view shape as the fixture inbox, pointed at live GIDs. */
export const liveTickets = [
  ticket({
    id: "t-unfulfilled",
    subject: "Has order #1001 left yet?",
    status: "open",
    view: "mine",
    assignee: "me",
    customerId: LIVE_IDS.C_UNFULFILLED,
    orderId: LIVE_IDS.O_1001,
    updatedAt: "2026-08-28T15:10:00Z",
    stubDraft: "Hi — order #1001 is paid and still unfulfilled. I will confirm when it is handed to the carrier.",
    stubSummary: "Customer asked whether #1001 has shipped. The order is paid and unfulfilled.",
    messages: [
      {
        id: "lm1",
        fromAgent: false,
        name: "Demo Unfulfilled",
        at: "2026-08-28T14:02:00Z",
        body: "Where is my order #1001? I do not see a shipment yet.",
      },
      {
        id: "lm2",
        fromAgent: true,
        name: STORE_NAME,
        at: "2026-08-28T14:40:00Z",
        body: "Looking at the order now — I will write back with the fulfillment update.",
      },
      { id: "ls1", kind: "status", at: "2026-08-28T14:41:00Z", body: "Assigned to me" },
    ],
  }),
  ticket({
    id: "t-fulfilled",
    subject: "Tracking on order #1002",
    status: "open",
    view: "unassigned",
    assignee: null,
    customerId: LIVE_IDS.C_FULFILLED,
    orderId: LIVE_IDS.O_1002,
    updatedAt: "2026-08-28T16:20:00Z",
    stubDraft: "Hi — #1002 is paid and fulfilled. Demo Carrier has it under AI-DEMO-1002.",
    stubSummary: "Customer asked for tracking on #1002. The order is fulfilled.",
    messages: [
      {
        id: "lm3",
        fromAgent: false,
        name: "Demo Fulfilled",
        at: "2026-08-28T16:20:00Z",
        body: "Please send the carrier link for order #1002.",
      },
    ],
  }),
  ticket({
    id: "t-multi-open",
    subject: "Question about order #1003",
    status: "open",
    view: "unassigned",
    assignee: null,
    customerId: LIVE_IDS.C_MULTI,
    orderId: LIVE_IDS.O_1003,
    updatedAt: "2026-08-27T11:05:00Z",
    stubDraft: "Hi — #1003 is paid and still unfulfilled. I will confirm when it ships.",
    stubSummary: "Customer asked about #1003. The order is paid and unfulfilled.",
    messages: [
      {
        id: "lm4",
        fromAgent: false,
        name: "Demo Multiple Orders",
        at: "2026-08-27T11:05:00Z",
        body: "When will order #1003 leave?",
      },
    ],
  }),
  ticket({
    id: "t-multi-snoozed",
    subject: "Do you ship the catalog to Canada?",
    status: "snoozed",
    view: "snoozed",
    assignee: null,
    customerId: LIVE_IDS.C_MULTI,
    orderId: null,
    updatedAt: "2026-08-26T09:00:00Z",
    stubDraft: "Hi — I can confirm the destination once an order exists.",
    stubSummary: "Customer asked about shipping to Canada. No order is attached.",
    messages: [
      {
        id: "lm5",
        fromAgent: false,
        name: "Demo Multiple Orders",
        at: "2026-08-26T09:00:00Z",
        body: "Do you ship the catalog to Canada, or is it local-only?",
      },
      { id: "ls2", kind: "status", at: "2026-08-26T09:05:00Z", body: "Set status: snoozed" },
    ],
  }),
  ticket({
    id: "t-fulfilled-closed",
    subject: "Received order #1002 — thank you",
    status: "closed",
    view: "closed",
    assignee: "me",
    customerId: LIVE_IDS.C_FULFILLED,
    orderId: LIVE_IDS.O_1002,
    updatedAt: "2026-08-25T18:12:00Z",
    stubDraft: "Glad #1002 arrived. I am here if anything comes up.",
    stubSummary: "Customer confirmed #1002 arrived. Ticket is closed.",
    messages: [
      {
        id: "lm6",
        fromAgent: false,
        name: "Demo Fulfilled",
        at: "2026-08-25T17:50:00Z",
        body: "Order #1002 arrived. Thank you — you can close this.",
      },
      {
        id: "lm7",
        fromAgent: true,
        name: STORE_NAME,
        at: "2026-08-25T18:10:00Z",
        body: "Glad it reached you.",
      },
      { id: "ls3", kind: "status", at: "2026-08-25T18:12:00Z", body: "Set status: closed" },
    ],
  }),
];
