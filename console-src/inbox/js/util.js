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

export function forbiddenControlHits(html) {
  const text = String(html || "").toLowerCase();
  const hits = [];
  if (/\bgaia\b/.test(text)) hits.push("Gaia");
  if (/\brefund\b/.test(text) && /<(button|a)\b/i.test(html)) {
    if (/<(button|a)[^>]*>[^<]*refund/i.test(html)) hits.push("Refund");
  }
  if (/<(button|a)[^>]*>[^<]*\bcancel\b/i.test(html)) hits.push("Cancel");
  if (/<(button|a)[^>]*>[^<]*edit(?:\s+order)?/i.test(html)) hits.push("Edit");
  return hits;
}
