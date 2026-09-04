import {
  addressPeek,
  esc,
  firstTracking,
  formatMoney,
  formatSku,
  formatWhen,
  hasTracking,
  lineFulfillmentLabel,
  shipmentPeek,
  statusLabel,
  TRACKING_MISSING_LABEL,
} from "../util.js";

/**
 * This-order rail tissue.
 * In: `{ shop, orderId }` via shop tissue.
 * Out: Clerk order DTO. Peek: name + Paid + Fulfilled.
 * Empty fulfillments/tracking: shipment peek "No tracking". Do not invent tracking.
 */
export function projectOrder(record) {
  if (!record) {
    return {
      ok: false,
      peek: "No order",
      record: null,
      skuLabels: [],
      addressPeek: "No address",
      hasTracking: false,
      tracking: null,
      shipmentPeek: TRACKING_MISSING_LABEL,
      lineFulfillLabels: [],
    };
  }
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
    shipmentPeek: shipmentPeek(record),
    lineFulfillLabels: nodes.map((item) => lineFulfillmentLabel(item)),
    record,
  };
}

function renderTrackingCopy(tracking) {
  const company = tracking.company
    ? `<span class="ship-company">${esc(tracking.company)}</span>`
    : "";
  const number = tracking.number
    ? `<span class="mono ship-number">${esc(tracking.number)}</span>`
    : "";
  const copy = company || number
    ? `<span class="ship-copy">${[company, number].filter(Boolean).join("")}</span>`
    : "";
  const track = tracking.url
    ? `<a class="track-link" href="${esc(tracking.url)}" rel="noreferrer" target="_blank">Track</a>`
    : "";
  return `<p class="ship-track">${copy}${track}</p>`;
}

function renderShipment(model, shipOpen) {
  const tracking = model.tracking;
  const shipLines = (model.record?.fulfillments || []).flatMap((fulfillment) =>
    (fulfillment.fulfillmentLineItems?.nodes || []).map((item) => {
      const title = item.lineItem?.title || "";
      const qty = item.quantity;
      if (!title) return "";
      return `<p class="ship-line">${esc(title)}${qty != null ? ` · ${esc(qty)}` : ""}</p>`;
    }),
  ).join("");
  if (model.hasTracking && tracking) {
    const peek = model.shipmentPeek
      ? ` <span class="peek">${esc(model.shipmentPeek)}</span>`
      : "";
    return `<div class="rail-sub" data-open="${shipOpen ? "true" : "false"}">
        <button type="button" class="rail-sub-toggle" data-toggle="shipment" aria-expanded="${shipOpen ? "true" : "false"}"><h3>Shipment</h3>${peek}</button>
        <div class="rail-sub-body"${shipOpen ? "" : " hidden"}>
          ${renderTrackingCopy(tracking)}
          ${shipLines}
        </div>
      </div>`;
  }
  return `<div class="rail-sub" data-open="${shipOpen ? "true" : "false"}">
      <button type="button" class="rail-sub-toggle" data-toggle="shipment" aria-expanded="${shipOpen ? "true" : "false"}">
        <h3>Shipment</h3> <span class="peek">${esc(model.shipmentPeek || TRACKING_MISSING_LABEL)}</span>
      </button>
      <div class="rail-sub-body"${shipOpen ? "" : " hidden"}>
        <p class="tissue-empty">${esc(TRACKING_MISSING_LABEL)}</p>
      </div>
    </div>`;
}

function renderAddress(label, address) {
  if (!address) return `<div class="addr"><h4>${esc(label)}</h4><p>Absent</p></div>`;
  const lines = [address.name, address.address1, address.address2, [address.city, address.province, address.zip].filter(Boolean).join(", "), address.country]
    .filter(Boolean);
  return `<div class="addr"><h4>${esc(label)}</h4>${lines.map((line) => `<p>${esc(line)}</p>`).join("")}</div>`;
}

export function renderOrder(model, { open = true, addressesOpen = false, shipmentOpen } = {}) {
  const record = model.record;
  const gateHairline = `<div class="order-gate">
      <button type="button" class="btn-hairline" data-write-gate-open>Payments locked</button>
    </div>`;
  if (!model.ok || !record) {
    return `<section class="rail-card" data-tissue="order" data-open="${open ? "true" : "false"}">
      <button type="button" class="rail-toggle" data-toggle="order" aria-expanded="${open ? "true" : "false"}">
        <h2>This order</h2><span class="peek">${esc(model.peek)}</span>
      </button>
      <div class="rail-body">
        <p class="tissue-empty">No order on this ticket</p>
        ${gateHairline}
      </div>
    </section>`;
  }
  const shipOpen = shipmentOpen == null ? model.hasTracking : shipmentOpen;
  const items = (record.lineItems?.nodes || []).map((item, index) => {
    const skuLabel = model.skuLabels[index] ?? formatSku(item.sku);
    const skuRow = skuLabel
      ? `<p class="mono line-sku" data-sku="${esc(skuLabel)}">${esc(skuLabel)}</p>`
      : "";
    const imageUrl = item.image?.url || "";
    const imageAlt = item.image?.altText || item.title || "Product";
    const thumb = imageUrl
      ? `<img class="line-thumb" src="${esc(imageUrl)}" alt="${esc(imageAlt)}" loading="lazy" />`
      : `<span class="line-thumb line-thumb-empty" aria-hidden="true"></span>`;
    const fulfillLabel = model.lineFulfillLabels?.[index] || lineFulfillmentLabel(item);
    const fulfillCue = fulfillLabel
      ? ` · <span data-line-fulfill="${esc(fulfillLabel)}">${esc(fulfillLabel)}</span>`
      : "";
    return `<li class="line">
      <div class="line-row">
        ${thumb}
        <div class="line-copy">
          <p class="line-title">${esc(item.title)}</p>
          ${skuRow}
          <p class="line-meta">${esc(item.quantity)} · <span class="mono">${esc(formatMoney(item.originalUnitPriceSet, ""))}</span>${fulfillCue}</p>
        </div>
      </div>
    </li>`;
  }).join("");
  const shipment = renderShipment(model, shipOpen);
  return `<section class="rail-card" data-tissue="order" data-open="${open ? "true" : "false"}">
    <button type="button" class="rail-toggle" data-toggle="order" aria-expanded="${open ? "true" : "false"}">
      <h2>This order</h2>
      <span class="peek">${esc(model.peek)}</span>
    </button>
    <div class="rail-body">
      <p class="mono order-name">${esc(record.name)}</p>
      <p class="mute">${esc(formatWhen(record.createdAt))}</p>
      <ul class="lines">${items}</ul>
      <dl class="totals">
        <div><dt>Subtotal</dt><dd class="mono">${esc(formatMoney(record.currentSubtotalPriceSet, "—"))}</dd></div>
        <div><dt>Shipping</dt><dd class="mono">${esc(formatMoney(record.totalShippingPriceSet, "—"))}</dd></div>
        <div><dt>Tax</dt><dd class="mono">${esc(formatMoney(record.totalTaxSet, "—"))}</dd></div>
        <div><dt>Total</dt><dd class="mono">${esc(formatMoney(record.currentTotalPriceSet, "—"))}</dd></div>
      </dl>
      ${gateHairline}
      <div class="rail-sub" data-open="${addressesOpen ? "true" : "false"}">
        <button type="button" class="rail-sub-toggle" data-toggle="addresses" aria-expanded="${addressesOpen ? "true" : "false"}">
          <h3>Addresses</h3> <span class="peek">${esc(model.addressPeek)}</span>
        </button>
        <div class="rail-sub-body addr-stack"${addressesOpen ? "" : " hidden"}>
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
