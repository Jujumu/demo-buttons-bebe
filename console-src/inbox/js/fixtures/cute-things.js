/**
 * Cute Things sandbox fixtures. Synthetic AI-DEMO records only.
 * SKUs are null. Returns are empty. Billing is often null.
 * No Gorgias customer names or live store identifiers from screenshots.
 */

export const SHOP = "yznyc1-ez.myshopify.com";
export const STORE_NAME = "Cute Things";

const ADA = "gid://shopify/Customer/51002";
const CASEY = "gid://shopify/Customer/51003";
const JORDAN = "gid://shopify/Customer/51005";

const ORDER_1002 = "gid://shopify/Order/7131035861165";
const ORDER_1003 = "gid://shopify/Order/7131035893933";
const ORDER_1004 = "gid://shopify/Order/7131035992237";

const dhakaShip = {
  name: "Ada Demo",
  address1: "12 Demo Lane",
  address2: null,
  city: "Dhaka",
  province: "Dhaka Division",
  zip: "1207",
  country: "Bangladesh",
};

export const customers = {
  [ADA]: {
    id: ADA,
    displayName: "Ada Demo",
    defaultEmailAddress: { emailAddress: "ai-demo-fulfilled@example.com" },
    createdAt: "2026-06-02T09:00:00Z",
    numberOfOrders: 1,
    amountSpent: { amount: "36.80", currencyCode: "BDT" },
    tags: ["AI-DEMO"],
  },
  [CASEY]: {
    id: CASEY,
    displayName: "Casey Sandbox",
    defaultEmailAddress: { emailAddress: "ai-demo-multi@example.com" },
    createdAt: "2026-06-04T11:30:00Z",
    numberOfOrders: 2,
    amountSpent: { amount: "220.80", currencyCode: "BDT" },
    tags: ["AI-DEMO"],
  },
  [JORDAN]: {
    id: JORDAN,
    displayName: "Jordan Preview",
    defaultEmailAddress: { emailAddress: "ai-demo-preview@example.com" },
    createdAt: "2026-07-12T14:00:00Z",
    numberOfOrders: 0,
    amountSpent: { amount: "0.00", currencyCode: "BDT" },
    tags: ["AI-DEMO"],
  },
};

function money(amount, currencyCode = "BDT") {
  return { shopMoney: { amount, currencyCode } };
}

export const orders = {
  [ORDER_1002]: {
    id: ORDER_1002,
    name: "#1002",
    createdAt: "2026-08-20T09:05:00Z",
    displayFinancialStatus: "PAID",
    displayFulfillmentStatus: "FULFILLED",
    currentTotalPriceSet: money("36.80"),
    currentSubtotalPriceSet: money("32.00"),
    totalShippingPriceSet: money("4.80"),
    totalTaxSet: money("0.00"),
    lineItems: {
      nodes: [
        {
          title: "Handcrafted Wooden Teether Toy",
          sku: null,
          quantity: 1,
          price: "32.00",
        },
      ],
    },
    shippingAddress: { ...dhakaShip, name: "Ada Demo" },
    billingAddress: null,
    fulfillments: [
      {
        trackingInfo: [
          {
            number: "AI-DEMO-1002",
            company: "Demo Carrier",
            url: "https://example.com/ai-demo/1002",
          },
        ],
      },
    ],
    customerId: ADA,
  },
  [ORDER_1003]: {
    id: ORDER_1003,
    name: "#1003",
    createdAt: "2026-08-22T10:12:00Z",
    displayFinancialStatus: "PAID",
    displayFulfillmentStatus: "UNFULFILLED",
    currentTotalPriceSet: money("50.60"),
    currentSubtotalPriceSet: money("44.00"),
    totalShippingPriceSet: money("6.60"),
    totalTaxSet: money("0.00"),
    lineItems: {
      nodes: [
        {
          title: "Designer Linen Baby Sun Hat",
          sku: null,
          quantity: 1,
          price: "44.00",
        },
      ],
    },
    shippingAddress: {
      name: "Casey Sandbox",
      address1: "88 Fixture Road",
      address2: null,
      city: "Dhaka",
      province: "Dhaka Division",
      zip: "1212",
      country: "Bangladesh",
    },
    billingAddress: null,
    fulfillments: [],
    customerId: CASEY,
  },
  [ORDER_1004]: {
    id: ORDER_1004,
    name: "#1004",
    createdAt: "2026-08-24T08:40:00Z",
    displayFinancialStatus: "PAID",
    displayFulfillmentStatus: "FULFILLED",
    currentTotalPriceSet: money("170.20"),
    currentSubtotalPriceSet: money("148.00"),
    totalShippingPriceSet: money("22.20"),
    totalTaxSet: money("0.00"),
    lineItems: {
      nodes: [
        {
          title: "Cashmere Knit Baby Blanket",
          sku: null,
          quantity: 1,
          price: "148.00",
        },
      ],
    },
    shippingAddress: {
      name: "Casey Sandbox",
      address1: "88 Fixture Road",
      address2: null,
      city: "Dhaka",
      province: "Dhaka Division",
      zip: "1212",
      country: "Bangladesh",
    },
    billingAddress: {
      name: "Casey Sandbox",
      address1: "4 Preview Court",
      address2: null,
      city: "Dhaka",
      province: "Dhaka Division",
      zip: "1205",
      country: "Bangladesh",
    },
    fulfillments: [
      {
        trackingInfo: [
          {
            number: "AI-DEMO-1004",
            company: "Demo Carrier",
            url: "https://example.com/ai-demo/1004",
          },
        ],
      },
    ],
    customerId: CASEY,
  },
};

/** Empty returns for every Cute Things fixture order. */
export const emptyReturns = {
  returns: { nodes: [] },
  returnStatus: null,
  inProgress: false,
  items: [],
  refundTotal: null,
  creditTotal: null,
  tracking: null,
};

export const views = [
  { id: "mine", label: "Assigned to me" },
  { id: "unassigned", label: "Unassigned" },
  { id: "all", label: "All" },
  { id: "snoozed", label: "Snoozed" },
  { id: "closed", label: "Closed" },
];

export const macros = [
  { id: "where", name: "Where is my order", tags: ["shipping"], body: "Thanks for writing in — I am checking the shipment on this order now." },
  { id: "ship", name: "Shipping timeline", tags: ["shipping"], body: "Demo store shipping usually leaves within a few days of the paid order." },
  { id: "care", name: "Care notes", tags: ["product"], body: "Happy to share care notes for the item on this order." },
];

export const tickets = [
  {
    id: "t-ada-track",
    subject: "Tracking on order #1002 has not moved",
    status: "open",
    view: "mine",
    assignee: "me",
    customerId: ADA,
    orderId: ORDER_1002,
    updatedAt: "2026-08-28T15:10:00Z",
    stubDraft: "Hi Ada — order #1002 is paid and fulfilled. Demo Carrier has it under AI-DEMO-1002.",
    stubSummary: "Ada asked where #1002 is. The order is fulfilled with Demo Carrier tracking.",
    messages: [
      {
        id: "m1",
        fromAgent: false,
        name: "Ada Demo",
        at: "2026-08-28T14:02:00Z",
        body: "Where is my order #1002? The tracking has not updated.",
      },
      {
        id: "m2",
        fromAgent: true,
        name: "Cute Things",
        at: "2026-08-28T14:40:00Z",
        body: "Looking at the shipment now — I will write back with the carrier update.",
      },
      { id: "s1", kind: "status", at: "2026-08-28T14:41:00Z", body: "Assigned to me" },
    ],
  },
  {
    id: "t-casey-hat",
    subject: "When will order #1003 ship?",
    status: "open",
    view: "unassigned",
    assignee: null,
    customerId: CASEY,
    orderId: ORDER_1003,
    updatedAt: "2026-08-28T16:20:00Z",
    stubDraft: "Hi Casey — #1003 is paid and still unfulfilled. I will confirm when it is handed to the carrier.",
    stubSummary: "Casey asked when the sun hat in #1003 will ship. The order is paid and unfulfilled.",
    messages: [
      {
        id: "m3",
        fromAgent: false,
        name: "Casey Sandbox",
        at: "2026-08-28T16:20:00Z",
        body: "Please tell me when order #1003 will leave. I need the sun hat this week.",
      },
    ],
  },
  {
    id: "t-casey-blanket",
    subject: "Question about the blanket on #1004",
    status: "open",
    view: "unassigned",
    assignee: null,
    customerId: CASEY,
    orderId: ORDER_1004,
    updatedAt: "2026-08-27T11:05:00Z",
    stubDraft: "Hi Casey — #1004 is paid and fulfilled. The cashmere blanket is with Demo Carrier as AI-DEMO-1004.",
    stubSummary: "Casey asked about the blanket on #1004. The order is fulfilled.",
    messages: [
      {
        id: "m4",
        fromAgent: false,
        name: "Casey Sandbox",
        at: "2026-08-27T11:05:00Z",
        body: "Did the cashmere blanket on #1004 go out? I want to confirm the shipment.",
      },
    ],
  },
  {
    id: "t-jordan-ship",
    subject: "Do you ship the demo catalog to Canada?",
    status: "snoozed",
    view: "snoozed",
    assignee: null,
    customerId: JORDAN,
    orderId: null,
    updatedAt: "2026-08-26T09:00:00Z",
    stubDraft: "Hi Jordan — this Cute Things demo ships the fixture catalog on the published demo timeline. I can confirm the destination once an order exists.",
    stubSummary: "Jordan asked whether the demo catalog ships to Canada. No order is attached.",
    messages: [
      {
        id: "m5",
        fromAgent: false,
        name: "Jordan Preview",
        at: "2026-08-26T09:00:00Z",
        body: "Do you ship the demo catalog to Canada, or is it local-only?",
      },
      { id: "s2", kind: "status", at: "2026-08-26T09:05:00Z", body: "Set status: snoozed" },
    ],
  },
  {
    id: "t-ada-closed",
    subject: "Received the teether — thank you",
    status: "closed",
    view: "closed",
    assignee: "me",
    customerId: ADA,
    orderId: ORDER_1002,
    updatedAt: "2026-08-25T18:12:00Z",
    stubDraft: "Glad #1002 arrived, Ada. I am here if anything about the teether comes up.",
    stubSummary: "Ada confirmed the teether from #1002 arrived. Ticket is closed.",
    messages: [
      {
        id: "m6",
        fromAgent: false,
        name: "Ada Demo",
        at: "2026-08-25T17:50:00Z",
        body: "The teether from #1002 arrived. Thank you — you can close this.",
      },
      {
        id: "m7",
        fromAgent: true,
        name: "Cute Things",
        at: "2026-08-25T18:10:00Z",
        body: "Glad it reached you, Ada.",
      },
      { id: "s3", kind: "status", at: "2026-08-25T18:12:00Z", body: "Set status: closed" },
    ],
  },
];

export const IDS = {
  ADA,
  CASEY,
  JORDAN,
  ORDER_1002,
  ORDER_1003,
  ORDER_1004,
};

export function ticketInView(ticket, viewId) {
  if (viewId === "all") return true;
  if (viewId === "mine") return ticket.assignee === "me" && ticket.status === "open";
  if (viewId === "unassigned") return ticket.assignee == null && ticket.status === "open";
  if (viewId === "snoozed") return ticket.status === "snoozed";
  if (viewId === "closed") return ticket.status === "closed";
  return false;
}

export function viewCounts(list = tickets) {
  return Object.fromEntries(views.map((view) => [
    view.id,
    list.filter((ticket) => ticketInView(ticket, view.id)).length,
  ]));
}
