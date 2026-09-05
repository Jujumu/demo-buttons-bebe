import { clerkTicket, clerkTicketRow } from "./clerk-ticket.js";
import { customers, emptyReturns, macros as fixtureMacros, orders, returnsForOrder, SHOP, ticketInView, tickets as fixtureTickets } from "../fixtures/demo-inbox.js";
import { REQUEST_TYPE_BUG, REQUEST_TYPE_PRIVACY, REQUEST_TYPE_UNSUBSCRIBE } from "../util.js";

function assertShop(shop) {
  if (shop && shop !== SHOP) {
    throw new Error("shop tissue refused an unknown fixture shop");
  }
}

function historyRow(order) {
  const shopMoney = order.currentTotalPriceSet?.shopMoney;
  return {
    id: order.id,
    name: order.name,
    createdAt: order.createdAt,
    displayFulfillmentStatus: order.displayFulfillmentStatus,
    currentTotalPriceSet: shopMoney ? { shopMoney: { ...shopMoney } } : { shopMoney: { amount: "0.00", currencyCode: "USD" } },
  };
}

function titleCase(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function ticketCustomerName(thread) {
  if (thread.customerName) return String(thread.customerName);
  for (const message of thread.messages || []) {
    if (message.kind === "status" || message.fromAgent === true) continue;
    if (message.name) return String(message.name);
  }
  return "";
}

function trackingOf(order) {
  for (const fulfillment of order?.fulfillments || []) {
    for (const info of fulfillment.trackingInfo || []) {
      const number = String(info.number || "").trim();
      if (number) return { company: String(info.company || "").trim(), number };
    }
  }
  return { company: "", number: "" };
}

function hasOpenReturn(returns) {
  if (!returns) return false;
  if (returns.inProgress === true) return true;
  return (returns.returns?.nodes || []).some((node) => String(node.status || "") === "OPEN");
}

/** Typed fixture drafts. Never invent order, catalog, or destination copy. */
export function draftForRequestType(requestType, name) {
  const who = String(name || "").trim() || "there";
  if (requestType === REQUEST_TYPE_UNSUBSCRIBE) {
    return `Hi ${who} — I have your marketing unsubscribe request. I will confirm the preference out of band. This inbox does not change Shopify marketing settings.`;
  }
  if (requestType === REQUEST_TYPE_PRIVACY) {
    return `Hi ${who} — I have your privacy request. I will handle the data export or deletion out of band. This inbox does not write Shopify Customer Privacy.`;
  }
  if (requestType === REQUEST_TYPE_BUG) {
    return `Hi ${who} — I have your bug report. Reply with the device you reproduced this on (iOS or Android). This inbox does not invent order or catalog answers.`;
  }
  return "";
}

function scenarioDraft(ticketId, name, orderName, financial, fulfill) {
  const oid = orderName || "";
  const money = financial || "Paid";
  const ship = fulfill || "Unfulfilled";
  if (ticketId === "t-demo-04-return") {
    const looked = oid || "#1003";
    return `Hi ${name} — I looked at ${looked}. To start a return on the merino throw, reply with the item name and whether tags are still on, and we will walk you through the return portal steps from here. A prepaid label is not automatic — once the return is set up, we will confirm whether a label is included or you need to buy postage. I will not refund or cancel from this chat. Let me know if you need anything else.`;
  }
  if (ticketId === "t-demo-05-cancel") {
    const looked = oid || "#1001";
    return `Hi ${name} — I looked at ${looked}. It is ${money} and ${ship}, so it has not been handed to a carrier yet. I see you asked to cancel because of the wrong size. I will not cancel or refund from here — a teammate needs to review the hold before anything changes. I will write back once that review is done. Let me know if you need anything else.`;
  }
  if (ticketId === "t-demo-08-canada") {
    return `Hi ${name} — Yes, we can ship the Muslin Swaddle Trio to Montreal. International shipping is offered at checkout (about $35 USD as a typical rate — please confirm the live total before you place the order). Any customs or import duties charged in Canada are the customer’s responsibility. I cannot promise a carrier delivery date from this chat. Let me know if you need anything else.`;
  }
  if (ticketId === "t-demo-14-duplicate") {
    const looked = oid || "#1001";
    return `Hi ${name} — I looked at ${looked}. Thanks for flagging the two bank lines that look like this order. I am checking whether one is a pending authorization versus a second capture. I will not refund from here — once we confirm what the bank is showing, a teammate can advise next steps. Let me know if you need anything else.`;
  }
  if (ticketId === "t-demo-18-exchange") {
    const looked = oid || "#1003";
    return `Hi ${name} — I looked at ${looked}. Happy to help with an exchange on the Organic Cotton Bath Towel Hood for the next size. Reply with the size you want and whether the current towel is unused with tags on, and we will outline the swap steps from here. I will not issue a refund from this chat. Let me know if you need anything else.`;
  }
  if (ticketId === "t-demo-22-policy") {
    return `Hi ${name} — For unused baby apparel with tags still on, our demo return window is 7 days after delivery for refund eligibility — the return needs a carrier scan within that window. After that, eligible returns are usually store credit instead. Final-sale items follow different rules. I will not process a refund from this chat; write back with an order number if you want us to check a specific item. Let me know if you need anything else.`;
  }
  if (ticketId === "t-demo-03-damaged-rattle" || ticketId === "t-demo-17-plush" || ticketId === "t-demo-12-damaged-box") {
    return `Hi ${name} — Thanks for the photo of the damage. I am sorry it arrived that way. Reply with your order number (like #1001) so I can look this up, and we will sort next steps from here. I will not refund from this chat. Let me know if you need anything else.`;
  }
  return "";
}

function looksLikeDamage(asked, subject = "") {
  const blob = `${asked || ""} ${subject || ""}`.toLowerCase();
  return /torn|tear|cracked|crack|damaged|damage|broke|broken|seam|ripped/.test(blob);
}

function customerPhotoCount(thread) {
  let total = 0;
  for (const message of thread.messages || []) {
    if (message.kind === "status" || message.fromAgent === true) continue;
    const attachments = message.attachments || [];
    if (Array.isArray(attachments)) {
      total += attachments.filter((item) => item && item.url).length;
    }
  }
  return total;
}

/** Labeled fixture draft from already-loaded thread + rail DTOs. Never displayName. */
export function fixtureDraftFromThread(thread = {}, rail = {}) {
  const full = ticketCustomerName(thread);
  const name = full.trim().split(/\s+/)[0] || "there";
  const typed = draftForRequestType(thread.requestType, name);
  if (typed) return typed;
  const status = String(thread.status || "").toLowerCase();
  const order = rail.order && typeof rail.order === "object" ? rail.order : {};
  const orderName = String(order.name || "").trim();
  const financial = titleCase(order.displayFinancialStatus);
  const fulfill = titleCase(order.displayFulfillmentStatus);
  const ticketId = String(thread.id || "").trim();
  const scenario = scenarioDraft(ticketId, name, orderName, financial, fulfill);
  if (scenario) return scenario;
  const asked = (() => {
    for (const message of [...(thread.messages || [])].reverse()) {
      if (message.kind === "status" || message.fromAgent === true) continue;
      if (message.body) return String(message.body).trim();
    }
    return String(thread.snippet || thread.subject || "").trim();
  })();
  if (!orderName && looksLikeDamage(asked, thread.subject)) {
    const photos = customerPhotoCount(thread);
    const photoBit = photos ? "Thanks for the photo of the damage. " : "Thanks for flagging the damage. ";
    return `Hi ${name} — ${photoBit}I am sorry it arrived that way. Reply with your order number (like #1001) so I can look this up, and we will sort next steps from here. I will not refund from this chat. Let me know if you need anything else.`;
  }
  if (thread.stubDraft) return thread.stubDraft;
  const { company, number } = trackingOf(order);
  const sentences = [];
  if (status === "closed") {
    sentences.push(`Glad this reached you, ${name}.`);
    sentences.push(orderName
      ? `${orderName} can stay closed — write back if anything else comes up.`
      : "I am here if anything else comes up.");
    return sentences.join(" ");
  }
  const greet = `Hi ${name} —`;
  if (orderName && financial && fulfill) {
    sentences.push(`${greet} I looked at ${orderName}. It is ${financial} and ${fulfill}.`);
  } else if (orderName) {
    sentences.push(`${greet} I looked at ${orderName}.`);
  } else {
    sentences.push(`${greet} Happy to help once an order is on this ticket.`);
  }
  if (number) {
    sentences.push(`The carrier update is ${company ? `${company} ${number}` : number}.`);
  } else if (orderName && fulfill.toLowerCase() === "unfulfilled") {
    sentences.push("It has not been handed to a carrier yet. I will write back when it ships.");
  }
  if (hasOpenReturn(rail.returns)) {
    sentences.push("There is an open return on this order. I will not refund or cancel from here.");
  }
  sentences.push("Let me know if you need anything else.");
  return sentences.join(" ");
}

/**
 * Fixture shop tissue. Fallback when helpdesk mint/Admin is unavailable.
 * Same Clerk DTO shapes as helpdesk.get_customer / get_order / get_returns /
 * list_past_orders. No network, no mutations.
 *
 * @param {{ fail?: Record<string, Error | string> }} [opts]
 */
export function createFixtureShop(opts = {}) {
  const fail = opts.fail || {};
  const escalated = new Map();

  function maybeFail(key) {
    if (!fail[key]) return;
    throw fail[key] instanceof Error ? fail[key] : new Error(String(fail[key]));
  }

  function withEscalate(ticket) {
    const extra = escalated.get(ticket.id);
    if (!extra) return ticket;
    return {
      ...ticket,
      escalated: true,
      escalationReason: extra.reason || ticket.escalationReason,
      statusEvents: [
        ...(ticket.statusEvents || []),
        extra.event,
      ].filter(Boolean),
    };
  }

  return {
    id: "shop",
    shop: SHOP,
    getCustomer({ shop, customerId }) {
      assertShop(shop);
      maybeFail("customer");
      return customers[customerId] || null;
    },
    getOrder({ shop, orderId }) {
      assertShop(shop);
      maybeFail("order");
      if (!orderId) return null;
      return orders[orderId] || null;
    },
    getReturns({ shop, orderId }) {
      assertShop(shop);
      maybeFail("returns");
      if (!orderId || !orders[orderId]) {
        return { ...emptyReturns, returns: { nodes: [] }, items: [] };
      }
      return returnsForOrder(orderId);
    },
    getOrderHistory({ shop, customerId }) {
      assertShop(shop);
      maybeFail("order-history");
      return Object.values(orders)
        .filter((order) => order.customerId === customerId)
        .map(historyRow)
        .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
    },
    listTickets({ view, limit } = {}) {
      maybeFail("list");
      const cap = Number(limit) > 0 ? Number(limit) : 20;
      return fixtureTickets
        .filter((ticket) => ticketInView(ticket, view || "open"))
        .slice(0, cap)
        .map(clerkTicketRow);
    },
    getTicket({ ticketId } = {}) {
      maybeFail("thread");
      const ticket = fixtureTickets.find((row) => row.id === ticketId);
      return ticket ? clerkTicket(withEscalate(ticket)) : null;
    },
    draftReply(args = {}) {
      maybeFail("draft");
      const thread = args.thread || {};
      return {
        source: "sample",
        draft: fixtureDraftFromThread(thread, args),
      };
    },
    summarizeThread(args = {}) {
      maybeFail("summarize");
      const thread = args.thread || {};
      return {
        source: "sample",
        summary: thread.stubSummary || "",
      };
    },
    searchMacros(args = {}) {
      maybeFail("macros");
      const needle = String(args.query || "").trim().toLowerCase();
      const rows = fixtureMacros.filter((macro) => {
        if (!needle) return true;
        const hay = `${macro.id} ${macro.title} ${(macro.tags || []).join(" ")} ${macro.body}`.toLowerCase();
        return hay.includes(needle);
      });
      return { source: "sample", macros: rows.map((macro) => ({ ...macro })) };
    },
    applyMacro(args = {}) {
      maybeFail("apply-macro");
      const macro = fixtureMacros.find((item) => item.id === args.macroId);
      if (!macro) {
        throw new Error("macro not found");
      }
      const mode = args.mode === "append" ? "append" : "replace";
      const current = String(args.currentBody || "");
      const text = mode === "append" && current.trim() ? `${current.trimEnd()}\n\n${macro.body}` : macro.body;
      return {
        source: "sample",
        text,
        title: macro.title,
        mode,
        body: macro.body,
        macroId: macro.id,
      };
    },
    escalateTicket({ ticketId, reason } = {}) {
      maybeFail("escalate");
      const ticket = fixtureTickets.find((row) => row.id === ticketId);
      if (!ticket) return null;
      const note = reason ? `escalated: ${String(reason).trim()}` : "escalated";
      escalated.set(ticket.id, {
        reason: reason ? String(reason).trim() : "",
        event: { at: new Date().toISOString(), status: ticket.status, note },
      });
      return clerkTicket(withEscalate(ticket));
    },
    markPrivacyHandled({ ticketId } = {}) {
      maybeFail("privacy-handled");
      const ticket = fixtureTickets.find((row) => row.id === ticketId);
      if (!ticket || ticket.requestType !== "privacy_request") return null;
      ticket.privacyHandled = true;
      ticket.statusEvents = [
        ...(ticket.statusEvents || []),
        { at: new Date().toISOString(), status: ticket.status, note: "privacy handled" },
      ];
      return clerkTicket(withEscalate(ticket));
    },
    markUnsubscribed({ ticketId } = {}) {
      maybeFail("unsubscribe-handled");
      const ticket = fixtureTickets.find((row) => row.id === ticketId);
      if (!ticket || ticket.requestType !== "marketing_unsubscribe") return null;
      ticket.unsubscribeHandled = true;
      ticket.statusEvents = [
        ...(ticket.statusEvents || []),
        { at: new Date().toISOString(), status: ticket.status, note: "unsubscribed" },
      ];
      return clerkTicket(withEscalate(ticket));
    },
    markBugHandled({ ticketId } = {}) {
      maybeFail("bug-handled");
      const ticket = fixtureTickets.find((row) => row.id === ticketId);
      if (!ticket || ticket.requestType !== "bug") return null;
      ticket.bugHandled = true;
      ticket.statusEvents = [
        ...(ticket.statusEvents || []),
        { at: new Date().toISOString(), status: ticket.status, note: "bug handled" },
      ];
      return clerkTicket(withEscalate(ticket));
    },
    writeGateStatus() {
      maybeFail("write-gate");
      return {
        mutationsEnabled: false,
        refused: ["send", "refund", "cancel"],
        tools: ["helpdesk.send", "helpdesk.refund", "helpdesk.cancel"],
        message: "Shopify writes are refused. SHOPIFY_MUTATIONS_ENABLED stays 0.",
      };
    },
  };
}
