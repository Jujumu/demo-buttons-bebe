export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);
}

export function formatMoney(money, fallback = "") {
  if (!money) return fallback;
  const amount = money.amount ?? money.shopMoney?.amount;
  const currency = money.currencyCode ?? money.shopMoney?.currencyCode;
  if (amount == null) return fallback;
  return currency ? `${amount} ${currency}` : String(amount);
}

export function formatSku(sku) {
  if (sku == null || sku === "") return "";
  const text = String(sku).trim();
  if (text === "" || text === "null" || text === "undefined") return "";
  return text;
}

export function formatOrderCount(n) {
  const count = Number(n) || 0;
  return `${count} ${count === 1 ? "order" : "orders"}`;
}

export function formatWhen(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Status-event mute line: `Closed · Tuesday`. */
export function formatWeekday(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-GB", { weekday: "long", timeZone: "UTC" });
}

export function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "·";
  return parts.slice(0, 2).map((part) => part[0].toUpperCase()).join("");
}

export function addressesDiffer(shipping, billing) {
  if (!billing) return true;
  if (!shipping) return true;
  const keys = ["address1", "address2", "city", "province", "zip", "country"];
  return keys.some((key) => String(shipping[key] || "") !== String(billing[key] || ""));
}

export function addressPeek(shipping, billing) {
  if (!shipping && !billing) return "No address";
  if (!billing) return "No billing";
  if (!shipping) return "No shipping";
  if (addressesDiffer(shipping, billing)) return "Ship ≠ bill";
  return "Same address";
}

/** Empty fulfillments / no trackingInfo. Parallel to "No billing" / "No returns". */
export const TRACKING_MISSING_LABEL = "No tracking";
export const GIFT_CARDS_MISSING_LABEL = "No gift cards";
export const DISCOUNTS_MISSING_LABEL = "No discounts";
export const INVOICE_MISSING_LABEL = "No invoice";
export const WARRANTY_MISSING_LABEL = "No warranty";
export const ETA_MISSING_LABEL = "No ETA";

export function giftCardHint(card) {
  if (!card) return "";
  const masked = String(card.maskedCode || "").trim();
  if (masked) return masked;
  const last = String(card.lastCharacters || "").trim();
  return last ? `••••${last}` : "";
}

export function giftCardPeek(cards) {
  const list = Array.isArray(cards) ? cards.filter(Boolean) : [];
  if (!list.length) return GIFT_CARDS_MISSING_LABEL;
  return giftCardHint(list[0]) || GIFT_CARDS_MISSING_LABEL;
}

export function giftCardStatusLabel(enabled) {
  return enabled ? "Enabled" : "Disabled";
}

export function discountPeek(codes) {
  const list = Array.isArray(codes) ? codes.map((code) => String(code || "").trim()).filter(Boolean) : [];
  if (!list.length) return DISCOUNTS_MISSING_LABEL;
  return list[0];
}

export function invoiceUrlOf(order) {
  const url = String(order?.invoiceUrl || "").trim();
  if (!url) return "";
  const lower = url.toLowerCase();
  if (lower.startsWith("https://") || lower.startsWith("http://") || url.startsWith("/docs/review/")) {
    return url;
  }
  return "";
}

export function invoicePeek(url) {
  return invoiceUrlOf({ invoiceUrl: url }) ? "Invoice" : INVOICE_MISSING_LABEL;
}

/** Fixture helpdesk DTO. Live Order has no official warranty field. */
export function warrantyOf(order) {
  const raw = order?.warranty;
  if (!raw || typeof raw !== "object") return null;
  const period = String(raw.period || "").trim();
  const status = String(raw.status || "").trim();
  const endsOn = String(raw.endsOn || "").trim();
  if (!period && !status && !endsOn) return null;
  return { period, status, endsOn };
}

export function formatWarrantyEndsOn(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const iso = raw.includes("T") ? raw : `${raw}T00:00:00Z`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const stamp = date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  return `Ends ${stamp}`;
}

export function warrantyPeek(warranty) {
  const row = warrantyOf({ warranty });
  if (!row) return WARRANTY_MISSING_LABEL;
  if (row.period && row.status) return `${row.period} · ${row.status}`;
  if (row.period) return row.period;
  if (row.status) return row.status;
  return formatWarrantyEndsOn(row.endsOn) || WARRANTY_MISSING_LABEL;
}

function parseEtaDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const iso = raw.includes("T") ? raw : `${raw}T00:00:00Z`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

/** Official Fulfillment.estimatedDeliveryAt, else fixture order.eta. */
export function etaOf(order) {
  const top = String(order?.eta || "").trim();
  if (parseEtaDate(top)) return top;
  for (const fulfillment of order?.fulfillments || []) {
    const raw = String(fulfillment?.estimatedDeliveryAt || "").trim();
    if (parseEtaDate(raw)) return raw;
  }
  return "";
}

/** Fixture shipping-zone label. Live Order has no official zone field. */
export function shippingZoneOf(order) {
  return String(order?.shippingZone || "").trim();
}

export function formatEta(value) {
  const date = parseEtaDate(value);
  if (!date) return "";
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `ETA ${days[date.getUTCDay()]} ${date.getUTCDate()} ${months[date.getUTCMonth()]}`;
}

export function formatShippingZone(zone) {
  const text = String(zone || "").trim();
  return text ? `Zone: ${text}` : "";
}

export function etaPeek(order) {
  const eta = formatEta(etaOf(order));
  if (eta) return eta;
  return formatShippingZone(shippingZoneOf(order)) || ETA_MISSING_LABEL;
}

export function shipmentPeek(order) {
  if (!hasTracking(order)) return TRACKING_MISSING_LABEL;
  const status = firstFulfillmentDisplayStatus(order);
  return status ? fulfillmentDisplayLabel(status) : "";
}

/** Official LineItem.unfulfilledQuantity cue. Miss → no invented status. */
export function lineFulfillmentLabel(item) {
  if (item == null || item.unfulfilledQuantity == null || item.unfulfilledQuantity === "") {
    return "";
  }
  const qty = Number(item.quantity);
  const left = Number(item.unfulfilledQuantity);
  if (!Number.isFinite(qty) || qty < 0 || !Number.isFinite(left) || left < 0) return "";
  if (left <= 0) return "Shipped";
  if (left >= qty) return "Unfulfilled";
  return `${left} of ${qty} unfulfilled`;
}

export function firstFulfillmentDisplayStatus(order) {
  for (const fulfillment of order?.fulfillments || []) {
    if (fulfillment?.displayStatus) return fulfillment.displayStatus;
  }
  return "";
}

/** Shopify FulfillmentDisplayStatus on-screen copy ("In transit"). */
export function fulfillmentDisplayLabel(value) {
  const labeled = statusLabel(value);
  if (!labeled) return "";
  return labeled.charAt(0) + labeled.slice(1).toLowerCase();
}

export function statusLabel(value) {
  if (!value) return "";
  const text = String(value).replace(/_/g, " ").toLowerCase();
  return text.replace(/\b\w/g, (ch) => ch.toUpperCase());
}

export function hasTracking(order) {
  return Boolean(firstTracking(order));
}

export function firstTracking(order) {
  const fulfillments = order?.fulfillments || [];
  for (const fulfillment of fulfillments) {
    const info = fulfillment?.trackingInfo?.[0];
    if (info?.number || info?.url) return info;
  }
  return null;
}

const WRITE_CONTROL = /<(button|a)\b[^>]*>\s*(?:customer\s+)?(edit|duplicate|refund|cancel|create\s+order)/i;
const WRITE_ATTR = /\bdata-(?:edit|duplicate|refund|cancel|create-order|customer-update)\b/i;

/** On-screen status word. Enums in data stay OPEN / PAID / etc. */
export function screenStatus(value) {
  return statusLabel(value);
}

export function forbiddenControlHits(html) {
  const text = String(html || "").toLowerCase();
  const hits = [];
  if (/\bgaia\b/.test(text)) hits.push("Gaia");
  if (WRITE_CONTROL.test(html) || WRITE_ATTR.test(html) || /\bcustomerupdate\b/i.test(html)) {
    const labeled = String(html).match(WRITE_CONTROL);
    const name = labeled?.[2] ? labeled[2].replace(/\s+/g, " ") : "write";
    const pretty = name.charAt(0).toUpperCase() + name.slice(1);
    if (/edit/i.test(name)) hits.push("Edit");
    else if (/refund/i.test(name)) hits.push("Refund");
    else if (/cancel/i.test(name)) hits.push("Cancel");
    else if (/duplicate/i.test(name)) hits.push("Duplicate");
    else if (/create/i.test(name)) hits.push("Create order");
    else hits.push(pretty);
  }
  if (/<(button|a)[^>]*>[^<]*refund/i.test(html)) hits.push("Refund");
  if (/<(button|a)[^>]*>[^<]*\bcancel\b/i.test(html)) hits.push("Cancel");
  if (/<(button|a)[^>]*>[^<]*\bedit\b/i.test(html)) hits.push("Edit");
  if (/<(button|a)[^>]*>[^<]*duplicate/i.test(html)) hits.push("Duplicate");
  if (/<(button|a)[^>]*>[^<]*create\s+order/i.test(html)) hits.push("Create order");
  return [...new Set(hits)];
}

export function railWriteControlHits(html) {
  const rail = String(html || "").match(/data-pane="rail"[\s\S]*?(?:data-pane="|$)/);
  const slice = rail ? rail[0] : String(html || "");
  return forbiddenControlHits(slice).filter((hit) => hit !== "Gaia");
}
