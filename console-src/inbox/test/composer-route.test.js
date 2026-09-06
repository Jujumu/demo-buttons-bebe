import test from "node:test";
import assert from "node:assert/strict";
import { createMailbox } from "../js/mailbox.js";
import { createComposerTissue } from "../js/tissues/composer.js";

test("composer shows local route when outbound is off", () => {
  const mailbox = createMailbox();
  const composer = createComposerTissue({ mailbox });
  composer.update({
    ticket: {
      id: "t-in-1",
      customerName: "Ada",
      fromEmail: "ada@example.com",
      source: "gorgias",
      status: "open",
      messages: [],
    },
    body: "Hello",
    bridgeStatus: {
      gorgiasEnabled: true,
      outboundEnabled: false,
    },
  });
  const html = composer.render();
  assert.match(html, /Demo: stays local/);
  assert.match(html, /data-send-route/);
});

test("composer shows Gorgias route when switch is on", () => {
  const mailbox = createMailbox();
  const composer = createComposerTissue({ mailbox });
  composer.update({
    ticket: {
      id: "t-in-1",
      customerName: "Ada",
      fromEmail: "ada@example.com",
      source: "gorgias",
      status: "open",
      messages: [],
    },
    body: "Hello",
    bridgeStatus: {
      gorgiasEnabled: true,
      outboundEnabled: true,
    },
  });
  const html = composer.render();
  assert.match(html, /Sends via Gorgias to ada@example\.com/);
});

test("composer shows email route for agentmail tickets", () => {
  const mailbox = createMailbox();
  const composer = createComposerTissue({ mailbox });
  composer.update({
    ticket: {
      id: "t-in-2",
      customerName: "Sam",
      fromEmail: "sam@example.com",
      source: "agentmail",
      status: "open",
      messages: [],
    },
    body: "Hello",
    bridgeStatus: {
      gorgiasEnabled: true,
      outboundEnabled: true,
    },
  });
  const html = composer.render();
  assert.match(html, /Sends by email to sam@example\.com/);
});
