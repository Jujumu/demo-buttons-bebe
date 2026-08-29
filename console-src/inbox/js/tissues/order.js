import {
  addressPeek,
  esc,
  firstTracking,
  formatMoney,
  formatSku,
  formatWhen,
  hasTracking,
  statusLabel,
} from "../util.js";

/**
 * This-order rail tissue.
 * In: `{ shop, orderId }` via shop tissue.
 * Out: Clerk order DTO. Peek: name + Paid + Fulfilled.
 */
export function projectOrder(record) {
  if (!record) return { ok: false, peek: "No order", record: null, skuLabels: [], addressPeek: "No address" };
  const nodes = record.lineItems?.nodes || [];
  return {
    ok: true,
    peek: [record.name, statusLabel(record.displayFinancialStatus), statusLabel(record.displayFulfillmentStatus)]
      .filter(Boolean)
      .join(" · "),
    skuLabels: nodes.map((item) => formatSku(item.sku)),
    addressPeek: addressPeek(record.shippingAddress, record.billingAddress),
    hasTracking: hasTracking(record),
    tracking: firstTracking(record),
    record,
  };
}

function renderAddress(label, address) {
  if (!address) return `<div class="addr"><h4>${esc(label)}</h4><p>Absent</p></div>`;
  const lines = [address.name, address.address1, address.address2, [address.city, address.province, address.zip].filter(Boolean).join(", "), address.country]
    .filter(Boolean);
  return `<div class="addr"><h4>${esc(label)}</h4>${lines.map((line) => `<p>${esc(line)}</p>`).join("")}</div>`;
}

export function renderOrder(model, { open = true, addressesOpen = false, shipmentOpen } = {}) {
  const record = model.record;
  if (!model.ok || !record) {
    return `<section class="rail-card" data-tissue="order" data-open="${open ? "true" : "false"}">
      <button type="button" class="rail-toggle" data-toggle="order" aria-expanded="${open ? "true" : "false"}">
        <span>This order</span><span class="peek">${esc(model.peek)}</span>
      </button>
      <div class="rail-body"><p class="tissue-empty">No order on this ticket</p></div>
    </section>`;
  }
  const shipOpen = shipmentOpen == null ? model.hasTracking : shipmentOpen;
  const items = (record.lineItems?.nodes || []).map((item, index) => (
    `<tr>
      <td>${esc(item.title)}</td>
      <td class="mono">${esc(model.skuLabels[index] || formatSku(item.sku))}</td>
      <td>${esc(item.quantity)}</td>
      <td class="mono">${esc(item.price)}</td>
    </tr>`
  )).join("");
  const tracking = model.tracking;
  const shipment = model.hasTracking && tracking
    ? `<div class="rail-sub" data-open="${shipOpen ? "true" : "false"}">
        <button type="button" class="rail-sub-toggle" data-toggle="shipment" aria-expanded="${shipOpen ? "true" : "false"}">Shipment</button>
        <div class="rail-sub-body">
          <a class="track-link" href="${esc(tracking.url)}" rel="noreferrer">${esc(tracking.company)} ${esc(tracking.number)}</a>
        </div>
      </div>`
    : "";
  return `<section class="rail-card" data-tissue="order" data-open="${open ? "true" : "false"}">
    <button type="button" class="rail-toggle" data-toggle="order" aria-expanded="${open ? "true" : "false"}">
      <span>This order</span>
      <span class="peek">${esc(model.peek)}</span>
    </button>
    <div class="rail-body">
      <p class="mono order-name">${esc(record.name)}</p>
      <p class="mute">${esc(formatWhen(record.createdAt))}</p>
      <table class="lines">
        <thead><tr><th>Item</th><th>SKU</th><th>Qty</th><th>Price</th></tr></thead>
        <tbody>${items}</tbody>
      </table>
      <dl class="totals">
        <div><dt>Subtotal</dt><dd class="mono">${esc(formatMoney(record.currentSubtotalPriceSet, "—"))}</dd></div>
        <div><dt>Shipping</dt><dd class="mono">${esc(formatMoney(record.totalShippingPriceSet, "—"))}</dd></div>
        <div><dt>Tax</dt><dd class="mono">${esc(formatMoney(record.totalTaxSet, "—"))}</dd></div>
        <div><dt>Total</dt><dd class="mono">${esc(formatMoney(record.currentTotalPriceSet, "—"))}</dd></div>
      </dl>
      <div class="rail-sub" data-open="${addressesOpen ? "true" : "false"}">
        <button type="button" class="rail-sub-toggle" data-toggle="addresses" aria-expanded="${addressesOpen ? "true" : "false"}">
          Addresses <span class="peek">${esc(model.addressPeek)}</span>
        </button>
        <div class="rail-sub-body addr-stack">
          ${renderAddress("Shipping", record.shippingAddress)}
          ${renderAddress("Billing", record.billingAddress)}
        </div>
      </div>
      ${shipment}
    </div>
  </section>`;
}

export function createOrderTissue({ shop }) {
  return {
    id: "order",
    async load({ shop: shopId, orderId }) {
      try {
        if (!orderId) return projectOrder(null);
        const record = await shop.getOrder({ shop: shopId, orderId });
        return projectOrder(record);
      } catch (err) {
        return { ok: false, peek: "Order error", record: null, error: String(err?.message || err), skuLabels: [], addressPeek: "—" };
      }
    },
    project: projectOrder,
    render: renderOrder,
  };
}
