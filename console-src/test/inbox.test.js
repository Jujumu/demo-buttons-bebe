const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

const source = fs.readFileSync(new URL("../inbox.html", `file://${__filename}`), "utf8");

test("four panes are locked to the specified widths", () => {
  assert.match(source, /grid-template-columns:200px 300px minmax\(0,1fr\) 300px/);
  assert.equal((source.match(/class="pane /g) || []).length, 4);
  assert.doesNotMatch(source, /fifth|Ask Gaia|gaia/i);
});

test("tokens and typeface follow the inbox lock", () => {
  assert.match(source, /--ground:#F4F0EA/);
  assert.match(source, /--surface:#FFFDF9/);
  assert.match(source, /--ink:#1C1916/);
  assert.match(source, /--mute:#5C564F/);
  assert.match(source, /--accent:#B5471D/);
  assert.match(source, /IBM Plex Sans/);
  assert.match(source, /IBM Plex Mono/);
  assert.doesNotMatch(source, /Inter/);
  assert.doesNotMatch(source, /indigo|purple|#5b21|#4f46e5|#7c3aed/i);
});

test("composer never sends from the draft strip", () => {
  const strip = source.slice(source.indexOf("draft-strip"), source.indexOf("composer-body"));
  assert.match(strip, />Insert</);
  assert.match(strip, />Discard</);
  assert.doesNotMatch(strip, />Send</);
  assert.match(source, /id="send" disabled/);
  assert.match(source, /id="send-close" disabled/);
  assert.match(source, /\.btn\.primary:disabled\{[^}]*background:var\(--ground\)/);
});

test("a11y hooks are present", () => {
  assert.match(source, /Skip to thread/);
  assert.match(source, /href="#thread"/);
  assert.match(source, /outline:var\(--focus\)/);
  assert.match(source, /2px solid #1C1916/);
  assert.match(source, /prefers-reduced-motion/);
  assert.match(source, /ev\.key!=="j"/);
});

test("fixtures and copy stay free of Gorgias screenshot PII", () => {
  for (const banned of ["Malky", "Sperber", "Gaia", "info@buttons", "gorgias.com"]) {
    assert.doesNotMatch(source, new RegExp(banned, "i"));
  }
});

test("inbox is fixture-only and does not advertise a live shop", () => {
  assert.match(source, /Fixture data/);
  assert.doesNotMatch(source, /yznyc1-ez|Cute Things|SHOPIFY_CLIENT|myshopify\.com/i);
});

test("rail reads locked Admin GraphQL fields and empty sandbox states", () => {
  assert.match(source, /ident\.data\.displayName/);
  assert.match(source, /defaultEmailAddress\.emailAddress/);
  assert.match(source, /displayFinancialStatus/);
  assert.match(source, /displayFulfillmentStatus/);
  assert.match(source, /currentTotalPriceSet/);
  assert.match(source, /lineItems/);
  assert.match(source, /shippingAddress/);
  assert.match(source, /billingAddress/);
  assert.match(source, /trackingInfo/);
  assert.match(source, /returnStatus/);
  assert.match(source, /No SKU/);
  assert.match(source, /"No "\+label\+"\."/);
  assert.match(source, /addrBlock\("billingAddress"/);
  assert.doesNotMatch(source, /ident\.data\.email[^A]/);
  assert.doesNotMatch(source, /order_number|display_name|financial_status/);
});
