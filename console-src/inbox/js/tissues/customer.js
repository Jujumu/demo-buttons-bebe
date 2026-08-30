import { esc, formatWhen } from "../util.js";

/**
 * Customer rail tissue.
 * In: `{ shop, customerId }` via shop tissue.
 * Out: Clerk customer DTO. Peek: displayName.
 */
export function projectCustomer(record) {
  if (!record) return { ok: false, peek: "No customer", record: null };
  return {
    ok: true,
    peek: record.displayName || "Customer",
    record: {
      displayName: record.displayName,
      defaultEmailAddress: record.defaultEmailAddress
        ? { emailAddress: record.defaultEmailAddress.emailAddress }
        : null,
      createdAt: record.createdAt,
      numberOfOrders: record.numberOfOrders,
      amountSpent: record.amountSpent,
      tags: record.tags || [],
    },
  };
}

export function renderCustomer(model, { open = true } = {}) {
  const record = model.record;
  const body = !model.ok || !record
    ? `<p class="tissue-empty">Customer unavailable</p>`
    : `<dl class="rail-dl">
        <div><dt>Name</dt><dd>${esc(record.displayName)}</dd></div>
        <div><dt>Email</dt><dd>${esc(record.defaultEmailAddress?.emailAddress || "—")}</dd></div>
        <div><dt>Customer since</dt><dd>${esc(formatWhen(record.createdAt))}</dd></div>
        <div><dt>Orders</dt><dd>${esc(record.numberOfOrders)}</dd></div>
        <div><dt>Spent</dt><dd>${esc(record.amountSpent ? `${record.amountSpent.amount} ${record.amountSpent.currencyCode}` : "—")}</dd></div>
        <div><dt>Tags</dt><dd>${esc((record.tags || []).join(", ") || "—")}</dd></div>
      </dl>`;
  return `<section class="rail-card" data-tissue="customer" data-open="${open ? "true" : "false"}">
    <button type="button" class="rail-toggle" data-toggle="customer" aria-expanded="${open ? "true" : "false"}">
      <h2>Customer</h2>
      <span class="peek">${esc(model.peek)}</span>
    </button>
    <div class="rail-body">${body}</div>
  </section>`;
}

export function createCustomerTissue({ shop }) {
  return {
    id: "customer",
    async load({ shop: shopId, customerId }) {
      try {
        const record = await shop.getCustomer({ shop: shopId, customerId });
        return projectCustomer(record);
      } catch (err) {
        return { ok: false, peek: "Customer error", record: null, error: String(err?.message || err) };
      }
    },
    project: projectCustomer,
    render: renderCustomer,
  };
}
