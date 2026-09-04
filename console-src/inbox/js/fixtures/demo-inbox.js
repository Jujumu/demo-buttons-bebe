/**
 * Invented inbox fixtures. Not a live shop.
 * SKUs are null — the rail omits the mono SKU row. Billing is often null
 * (Addresses peek: No billing). One OPEN return lives on Ada #1001.
 * Admin GraphQL 2026-07 ReturnStatus in-progress value is OPEN.
 */

export const SHOP = "demo-inbox.example";
export const STORE_NAME = "Demo Shop";

const ADA = "gid://shopify/Customer/90001";
const CASEY = "gid://shopify/Customer/90002";
const JORDAN = "gid://shopify/Customer/90003";
const SKY = "gid://shopify/Customer/9004";

const ORDER_1001 = "gid://shopify/Order/80001";
const ORDER_1002 = "gid://shopify/Order/80002";
const ORDER_1003 = "gid://shopify/Order/80003";
const ORDER_1004 = "gid://shopify/Order/9004";

export const customers = {
  [ADA]: {
    id: ADA,
    displayName: "Ada Demo",
    defaultEmailAddress: { emailAddress: "ada.demo@example.com" },
    createdAt: "2026-06-02T09:00:00Z",
    numberOfOrders: "1",
    amountSpent: { amount: "28.00", currencyCode: "USD" },
    tags: ["DEMO"],
    giftCards: [
      {
        id: "gid://shopify/GiftCard/80001",
        lastCharacters: "4291",
        maskedCode: "••••4291",
        enabled: true,
        balance: { amount: "25.00", currencyCode: "USD" },
      },
    ],
  },
  [CASEY]: {
    id: CASEY,
    displayName: "Casey Sandbox",
    defaultEmailAddress: { emailAddress: "casey.sandbox@example.com" },
    createdAt: "2026-06-04T11:30:00Z",
    numberOfOrders: "2",
    amountSpent: { amount: "96.00", currencyCode: "USD" },
    tags: ["DEMO"],
  },
  [JORDAN]: {
    id: JORDAN,
    displayName: "Jordan Preview",
    defaultEmailAddress: { emailAddress: "jordan.preview@example.com" },
    createdAt: "2026-07-12T14:00:00Z",
    numberOfOrders: "0",
    amountSpent: { amount: "0.00", currencyCode: "USD" },
    tags: ["DEMO"],
  },
  [SKY]: {
    id: SKY,
    displayName: "Sky Jensen",
    defaultEmailAddress: { emailAddress: "sky.jensen@example.com" },
    createdAt: "2026-07-14T10:00:00Z",
    numberOfOrders: "1",
    amountSpent: { amount: "50.00", currencyCode: "USD" },
    tags: ["DEMO"],
  },
};

function moneyBag(amount, currencyCode = "USD") {
  const money = { amount, currencyCode };
  return { shopMoney: { ...money }, presentmentMoney: { ...money } };
}

export const orders = {
  [ORDER_1001]: {
    id: ORDER_1001,
    name: "#1001",
    createdAt: "2026-08-20T09:05:00Z",
    displayFinancialStatus: "PAID",
    displayFulfillmentStatus: "FULFILLED",
    currentTotalPriceSet: moneyBag("28.00"),
    currentSubtotalPriceSet: moneyBag("24.00"),
    totalShippingPriceSet: moneyBag("4.00"),
    totalTaxSet: moneyBag("0.00"),
    lineItems: {
      nodes: [
        {
          title: "Oak Demo Rattle",
          sku: null,
          quantity: 1,
          unfulfilledQuantity: 0,
          originalUnitPriceSet: moneyBag("24.00"),
          image: {
            url: "https://images.pexels.com/photos/129722/pexels-photo-129722.jpeg?auto=compress&cs=tinysrgb&h=200&w=200&fit=crop",
            altText: "Oak Demo Rattle",
          },
        },
      ],
    },
    shippingAddress: {
      name: "Ada Demo",
      address1: "12 Demo Lane",
      address2: null,
      city: "Demo City",
      province: "Example State",
      zip: "00001",
      country: "Exampleland",
    },
    billingAddress: null,
    fulfillments: [
      {
        displayStatus: "IN_TRANSIT",
        trackingInfo: [
          {
            number: "DEMO-1001",
            company: "Demo Carrier",
            url: "https://example.com/track/demo-1001",
          },
        ],
      },
    ],
    discountCodes: ["WELCOME10"],
    invoiceUrl: "https://example.com/invoice/demo-1001",
    warranty: {
      period: "1 year",
      status: "Active",
      endsOn: "2027-03-12",
    },
    customerId: ADA,
  },
  [ORDER_1002]: {
    id: ORDER_1002,
    name: "#1002",
    createdAt: "2026-08-22T10:12:00Z",
    displayFinancialStatus: "PAID",
    displayFulfillmentStatus: "UNFULFILLED",
    currentTotalPriceSet: moneyBag("36.00"),
    currentSubtotalPriceSet: moneyBag("32.00"),
    totalShippingPriceSet: moneyBag("4.00"),
    totalTaxSet: moneyBag("0.00"),
    lineItems: {
      nodes: [
        {
          title: "Canvas Demo Visor",
          sku: null,
          quantity: 1,
          unfulfilledQuantity: 1,
          originalUnitPriceSet: moneyBag("32.00"),
          image: {
            url: "https://images.pexels.com/photos/38702945/pexels-photo-38702945.jpeg?auto=compress&cs=tinysrgb&h=200&w=200&fit=crop",
            altText: "Canvas Demo Visor",
          },
        },
      ],
    },
    shippingAddress: {
      name: "Casey Sandbox",
      address1: "88 Fixture Road",
      address2: null,
      city: "Demo City",
      province: "Example State",
      zip: "00002",
      country: "Exampleland",
    },
    billingAddress: null,
    fulfillments: [],
    customerId: CASEY,
  },
  [ORDER_1003]: {
    id: ORDER_1003,
    name: "#1003",
    createdAt: "2026-08-24T08:40:00Z",
    displayFinancialStatus: "PAID",
    displayFulfillmentStatus: "FULFILLED",
    currentTotalPriceSet: moneyBag("60.00"),
    currentSubtotalPriceSet: moneyBag("54.00"),
    totalShippingPriceSet: moneyBag("6.00"),
    totalTaxSet: moneyBag("0.00"),
    lineItems: {
      nodes: [
        {
          title: "Merino Demo Throw",
          sku: null,
          quantity: 1,
          unfulfilledQuantity: 0,
          originalUnitPriceSet: moneyBag("54.00"),
          image: {
            url: "https://images.pexels.com/photos/9448357/pexels-photo-9448357.jpeg?auto=compress&cs=tinysrgb&h=200&w=200&fit=crop",
            altText: "Merino Demo Throw",
          },
        },
      ],
    },
    shippingAddress: {
      name: "Casey Sandbox",
      address1: "88 Fixture Road",
      address2: null,
      city: "Demo City",
      province: "Example State",
      zip: "00002",
      country: "Exampleland",
    },
    billingAddress: {
      name: "Casey Sandbox",
      address1: "4 Preview Court",
      address2: null,
      city: "Demo City",
      province: "Example State",
      zip: "00005",
      country: "Exampleland",
    },
    fulfillments: [
      {
        displayStatus: "IN_TRANSIT",
        trackingInfo: [
          {
            number: "DEMO-1003",
            company: "Demo Carrier",
            url: "https://example.com/track/demo-1003",
          },
        ],
      },
    ],
    customerId: CASEY,
  },
  [ORDER_1004]: {
    id: ORDER_1004,
    name: "#9004",
    createdAt: "2026-08-25T09:15:00Z",
    displayFinancialStatus: "PAID",
    displayFulfillmentStatus: "PARTIALLY_FULFILLED",
    currentTotalPriceSet: moneyBag("50.00"),
    currentSubtotalPriceSet: moneyBag("46.00"),
    totalShippingPriceSet: moneyBag("4.00"),
    totalTaxSet: moneyBag("0.00"),
    lineItems: {
      nodes: [
        {
          title: "Muslin Swaddle",
          sku: null,
          quantity: 1,
          unfulfilledQuantity: 0,
          originalUnitPriceSet: moneyBag("28.00"),
          image: {
            url: "https://images.pexels.com/photos/9448357/pexels-photo-9448357.jpeg?auto=compress&cs=tinysrgb&h=200&w=200&fit=crop",
            altText: "Muslin swaddle",
          },
        },
        {
          title: "Knit Baby Booties",
          sku: null,
          quantity: 1,
          unfulfilledQuantity: 1,
          originalUnitPriceSet: moneyBag("18.00"),
          image: {
            url: "https://images.pexels.com/photos/6902351/pexels-photo-6902351.jpeg?auto=compress&cs=tinysrgb&h=200&w=200&fit=crop",
            altText: "Knit baby booties",
          },
        },
      ],
    },
    shippingAddress: {
      name: "Sky Jensen",
      address1: "22 Rest Lane",
      address2: null,
      city: "Demo City",
      province: "Example State",
      zip: "00004",
      country: "Exampleland",
    },
    billingAddress: null,
    fulfillments: [
      {
        displayStatus: "IN_TRANSIT",
        trackingInfo: [
          {
            number: "SAMPLE-9004",
            company: "Sample Carrier",
            url: "https://example.com/sample/9004",
          },
        ],
        fulfillmentLineItems: {
          nodes: [{ quantity: 1, lineItem: { title: "Muslin Swaddle" } }],
        },
      },
    ],
    customerId: SKY,
  },
};

/** Empty returns. Casey / Jordan / no-order stay empty. */
export const emptyReturns = {
  returns: { nodes: [] },
  items: [],
  refundTotal: null,
  creditTotal: null,
  tracking: null,
};

/** Invented OPEN return on Ada #1001 — the only default-open returns case. */
export const openReturn1001 = {
  returns: {
    nodes: [
      {
        id: "gid://shopify/Return/70001",
        status: "OPEN",
      },
    ],
  },
  items: [
    { title: "Oak Demo Rattle", reason: "Changed mind", type: "RETURN" },
  ],
  refundTotal: moneyBag("24.00"),
  creditTotal: null,
  tracking: {
    number: "DEMO-RET-1001",
    company: "Demo Carrier",
    url: "https://example.com/track/demo-ret-1001",
  },
};

export const returnsByOrder = {
  [ORDER_1001]: openReturn1001,
};

function cloneReturns(record) {
  return {
    ...record,
    returns: { nodes: [...(record.returns?.nodes || [])] },
    items: [...(record.items || [])],
    tracking: record.tracking ? { ...record.tracking } : null,
  };
}

export function returnsForOrder(orderId) {
  const record = returnsByOrder[orderId];
  return record ? cloneReturns(record) : cloneReturns(emptyReturns);
}

export const views = [
  { id: "mine", label: "Assigned to me" },
  { id: "unassigned", label: "Unassigned" },
  { id: "all", label: "All" },
  { id: "snoozed", label: "Snoozed" },
  { id: "closed", label: "Closed" },
];

export const macros = [
  {
    id: "shipping-delay",
    title: "Shipping delay",
    tags: ["shipping", "delay"],
    body: "Hi — this shipment is running behind the usual window. I am watching the carrier update and will write back when it moves.",
  },
  {
    id: "return-how-to",
    title: "Return how-to",
    tags: ["return", "howto"],
    body: "You can start a return from the link in your order email. Pack the unused item, add the label, and drop it with the carrier. Write back if the link is missing and I will point you to it.",
  },
  {
    id: "order-status",
    title: "Order status",
    tags: ["order", "status", "shipping"],
    body: "I looked at this order. Once it is paid I can share fulfillment and tracking from the catalog. Write back if you want the latest carrier note.",
  },
];

export const tickets = [
  {
    id: "t-ada-track",
    customerName: "Ada Demo",
    subject: "Tracking on order #1001 has not moved",
    snippet: "Where is my order #1001? The tracking has not updated.",
    status: "open",
    view: "mine",
    assignee: "me",
    customerId: ADA,
    orderId: ORDER_1001,
    updatedAt: "2026-08-28T15:10:00Z",
    stubDraft: "Hi Ada — order #1001 is paid and fulfilled. Demo Carrier has it under DEMO-1001.",
    stubSummary: "Ada asked where #1001 is. The order is fulfilled with Demo Carrier tracking.",
    messages: [
      {
        id: "m1",
        fromAgent: false,
        name: "Ada Demo",
        at: "2026-08-28T14:02:00Z",
        body: "Where is my order #1001? The tracking has not updated.",
      },
      {
        id: "m2",
        fromAgent: true,
        name: STORE_NAME,
        at: "2026-08-28T14:40:00Z",
        body: "Looking at the shipment now — I will write back with the carrier update.",
      },
    ],
    statusEvents: [
      { at: "2026-08-28T14:41:00Z", status: "open", note: "assigned" },
    ],
  },
  {
    id: "t-casey-visor",
    customerName: "Casey Sandbox",
    subject: "When will order #1002 ship?",
    snippet: "Please tell me when order #1002 will leave. I need the visor this week.",
    status: "open",
    view: "unassigned",
    assignee: null,
    customerId: CASEY,
    orderId: ORDER_1002,
    updatedAt: "2026-08-28T16:20:00Z",
    stubDraft: "Hi Casey — #1002 is paid and still unfulfilled. I will confirm when it is handed to the carrier.",
    stubSummary: "Casey asked when the visor in #1002 will ship. The order is paid and unfulfilled.",
    messages: [
      {
        id: "m3",
        fromAgent: false,
        name: "Casey Sandbox",
        at: "2026-08-28T16:20:00Z",
        body: "Please tell me when order #1002 will leave. I need the visor this week.",
      },
    ],
    statusEvents: [],
  },
  {
    id: "t-casey-throw",
    customerName: "Casey Sandbox",
    subject: "Question about the throw on #1003",
    snippet: "Did the merino throw on #1003 go out? I want to confirm the shipment.",
    status: "open",
    view: "unassigned",
    assignee: null,
    customerId: CASEY,
    orderId: ORDER_1003,
    updatedAt: "2026-08-27T11:05:00Z",
    stubDraft: "Hi Casey — #1003 is paid and fulfilled. The merino throw is with Demo Carrier as DEMO-1003.",
    stubSummary: "Casey asked about the throw on #1003. The order is fulfilled.",
    messages: [
      {
        id: "m4",
        fromAgent: false,
        name: "Casey Sandbox",
        at: "2026-08-27T11:05:00Z",
        body: "Did the merino throw on #1003 go out? I want to confirm the shipment.",
      },
    ],
    statusEvents: [],
  },
  {
    id: "t-jordan-ship",
    customerName: "Jordan Preview",
    subject: "Do you ship the demo catalog to Canada?",
    snippet: "Do you ship the demo catalog to Canada, or is it local-only?",
    status: "snoozed",
    view: "snoozed",
    assignee: null,
    customerId: JORDAN,
    orderId: null,
    updatedAt: "2026-08-26T09:00:00Z",
    stubDraft: "Hi Jordan — this demo shop ships the fixture catalog on the published demo timeline. I can confirm the destination once an order exists.",
    stubSummary: "Jordan asked whether the demo catalog ships to Canada. No order is attached.",
    messages: [
      {
        id: "m5",
        fromAgent: false,
        name: "Jordan Preview",
        at: "2026-08-26T09:00:00Z",
        body: "Do you ship the demo catalog to Canada, or is it local-only?",
      },
    ],
    statusEvents: [
      { at: "2026-08-26T09:05:00Z", status: "snoozed", note: "waiting" },
    ],
  },
  {
    id: "t-ada-closed",
    customerName: "Ada Demo",
    subject: "Received the rattle — thank you",
    snippet: "The rattle from #1001 arrived. Thank you — you can close this.",
    status: "closed",
    view: "closed",
    assignee: "me",
    customerId: ADA,
    orderId: ORDER_1001,
    updatedAt: "2026-08-25T18:12:00Z",
    stubDraft: "Glad #1001 arrived, Ada. I am here if anything about the rattle comes up.",
    stubSummary: "Ada confirmed the rattle from #1001 arrived. Ticket is closed.",
    messages: [
      {
        id: "m6",
        fromAgent: false,
        name: "Ada Demo",
        at: "2026-08-25T17:50:00Z",
        body: "The rattle from #1001 arrived. Thank you — you can close this.",
      },
      {
        id: "m7",
        fromAgent: true,
        name: STORE_NAME,
        at: "2026-08-25T18:10:00Z",
        body: "Glad it reached you, Ada.",
      },
    ],
    statusEvents: [
      { at: "2026-08-25T18:12:00Z", status: "closed", note: "answered" },
    ],
  },
  {
    id: "t-sky-rest",
    customerName: "Sky Jensen",
    subject: "Where's the rest of order #9004?",
    snippet: "The swaddle shipped — where's the rest?",
    status: "open",
    view: "unassigned",
    assignee: null,
    customerId: SKY,
    orderId: ORDER_1004,
    updatedAt: "2026-08-28T17:00:00Z",
    stubDraft: "Hi Sky — #9004 is paid and partially fulfilled. The Muslin Swaddle is with Sample Carrier as SAMPLE-9004. The Knit Baby Booties are still unfulfilled.",
    stubSummary: "Sky asked where the rest of #9004 is. The swaddle shipped; the booties have not.",
    messages: [
      {
        id: "m8",
        fromAgent: false,
        name: "Sky Jensen",
        at: "2026-08-28T16:50:00Z",
        body: "The Muslin Swaddle on #9004 shipped. Where's the rest? The Knit Baby Booties are still unfulfilled.",
      },
    ],
    statusEvents: [],
  },
];

export const IDS = {
  ADA,
  CASEY,
  JORDAN,
  SKY,
  ORDER_1001,
  ORDER_1002,
  ORDER_1003,
  ORDER_1004,
};

export function ticketInView(ticket, viewId) {
  if (viewId === "all") return true;
  if (viewId === "open") return ticket.status === "open";
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
