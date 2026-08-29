/**
 * UX Pro review blocks. Any hit fails the inbox PR.
 * These inspect rendered HTML, not tissue internals.
 */

const PURPLE = /#6[Bb]46[Cc]1|#7[Cc]3[Aa][Ee][Dd]|#5[Bb]21[Bb]6|#7[Cc]4[Dd][Ff][Ff]|#5[Cc]4[Dd][Ff][Ff]|#8[Bb]5[Cc][Ff]6|#a78bfa/i;

export function toggleExpanded(html, name) {
  const match = String(html).match(new RegExp(`data-toggle="${name}"[^>]*aria-expanded="(true|false)"`));
  return match ? match[1] === "true" : null;
}

export function tissueOpen(html, name) {
  const match = String(html).match(new RegExp(`data-tissue="${name}"[^>]*data-open="(true|false)"`));
  return match ? match[1] === "true" : null;
}

export function displayedSkus(html) {
  return [...String(html).matchAll(/data-sku="([^"]*)"/g)].map((match) => match[1]);
}

export function reviewBlockViolations(html) {
  const text = String(html);
  const hits = [];
  const customer = toggleExpanded(text, "customer");
  const order = toggleExpanded(text, "order");
  const returns = toggleExpanded(text, "returns");
  const history = toggleExpanded(text, "order-history");
  const addresses = toggleExpanded(text, "addresses");

  if (customer && order && returns && addresses && history) {
    hits.push("fully-open rail wall");
  }
  if (addresses && history && (returns || customer)) {
    hits.push("fully-open rail wall");
  }

  const returnsCard = text.match(/data-tissue="returns"[\s\S]*?(?:data-tissue="|$)/);
  const returnsPeek = /No returns/.test(returnsCard ? returnsCard[0] : text);
  if (returns === true && returnsPeek) {
    hits.push("empty returns open");
  }

  if (history === true) {
    hits.push("past orders open by default");
  }

  if (/\bAsk Gaia\b/i.test(text) || /\bGaia\b/i.test(text)) {
    hits.push("Gaia");
  }
  if (PURPLE.test(text) || /gorgias purple/i.test(text)) {
    hits.push("Gorgias purple");
  }

  for (const sku of displayedSkus(text)) {
    if (sku === "null" || sku === "undefined") hits.push("literal null SKU");
    if (sku === "—" || sku === "–" || sku === "-") hits.push("em dash SKU");
  }
  if (/<(?:td|p)[^>]*class="[^"]*mono[^"]*"[^>]*>\s*null\s*</i.test(text)) {
    hits.push("literal null SKU");
  }

  return [...new Set(hits)];
}
