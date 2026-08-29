import { MAILBOX_TOPICS } from "../contracts.js";
import { esc, formatWhen, statusLabel } from "../util.js";

/**
 * Past-orders rail tissue.
 * In: `{ shop, customerId }` via shop tissue.
 * Out: `{ id, name, createdAt, total, fulfillmentStatus }[]` newest first.
 * Click peeks a row. It does not replace This order.
 */
export function projectOrderHistory(rows) {
  const list = [...(rows || [])].sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  return {
    ok: true,
    peek: String(list.length),
    rows: list,
  };
}

export function renderOrderHistory(model, { open = false, peekedId = null } = {}) {
  const rows = (model.rows || []).map((row) => {
    const on = row.id === peekedId;
    return `<button type="button" class="history-row${on ? " is-peeked" : ""}" data-history="${esc(row.id)}">
      <span class="mono">${esc(row.name)}</span>
      <span>${esc(statusLabel(row.fulfillmentStatus))}</span>
      <span class="mono">${esc(row.total)}</span>
      <span class="mute">${esc(formatWhen(row.createdAt))}</span>
    </button>`;
  }).join("");
  return `<section class="rail-card" data-tissue="order-history" data-open="${open ? "true" : "false"}">
    <button type="button" class="rail-toggle" data-toggle="order-history" aria-expanded="${open ? "true" : "false"}">
      <span>Past orders</span>
      <span class="peek">${esc(model.peek)}</span>
    </button>
    <div class="rail-body">${rows || `<p class="tissue-empty">No past orders</p>`}</div>
  </section>`;
}

export function createOrderHistoryTissue({ shop, mailbox }) {
  return {
    id: "order-history",
    async load({ shop: shopId, customerId }) {
      try {
        const rows = await shop.getOrderHistory({ shop: shopId, customerId });
        return projectOrderHistory(rows);
      } catch (err) {
        return { ok: false, peek: "0", rows: [], error: String(err?.message || err) };
      }
    },
    project: projectOrderHistory,
    render: renderOrderHistory,
    bind(el) {
      el.onclick = (event) => {
        const row = event.target.closest("[data-history]");
        if (!row) return;
        mailbox.publish(MAILBOX_TOPICS.HISTORY_PEEK, { orderId: row.dataset.history });
      };
    },
  };
}
