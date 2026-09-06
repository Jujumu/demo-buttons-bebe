import test from "node:test";
import assert from "node:assert/strict";
import { createMailbox } from "../js/mailbox.js";
import { createComposerTissue } from "../js/tissues/composer.js";
import { ACTIVATE_SEND_MESSAGE } from "../js/send-access.js";

test("composer tells the human to activate send access", () => {
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
  assert.match(html, new RegExp(ACTIVATE_SEND_MESSAGE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(html, /data-send-route/);
  assert.doesNotMatch(html, /Sends via Gorgias/);
  assert.doesNotMatch(html, /Sends by email/);
});
