const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const test = require("node:test");

const source = fs.readFileSync(new URL("../index.html", `file://${__filename}`), "utf8");
const start = source.indexOf("function whatsappConnectionSummary(data){");
const end = source.indexOf("\n}\n\nfunction conns(){", start);

assert.notEqual(start, -1, "WhatsApp summary helper is present");
assert.notEqual(end, -1, "WhatsApp summary helper has a stable boundary");

const context = {};
vm.runInNewContext(`${source.slice(start, end + 2)};this.summary=whatsappConnectionSummary;`, context);
const summary = value => JSON.parse(JSON.stringify(context.summary(value)));

test("connection state transitions fail closed", () => {
  assert.deepEqual(summary({ state: "qr" }), {
    label: "Needs linking",
    detail: "Scan the QR in Notifications",
    healthy: false,
  });
  assert.deepEqual(summary({ state: "connected", owner: "15551234567@s.whatsapp.net" }), {
    label: "Connected",
    detail: "Linked device",
    healthy: true,
  });
  assert.deepEqual(summary(null), {
    label: "Status unavailable",
    detail: "Connection status could not be confirmed",
    healthy: false,
  });
});

test("only the explicit connected state is healthy", () => {
  for (const state of ["starting", "qr", "closed", "", null, undefined]) {
    assert.equal(summary(state == null ? null : { state }).healthy, false);
  }
});
