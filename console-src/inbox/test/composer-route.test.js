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

test('locked production Send and Send & close are clickable and emit only the local lock event',()=>{
 const mailbox=createMailbox();const composer=createComposerTissue({mailbox});
 composer.update({ticket:{id:'gorgias:1',status:'unknown'},body:'',capabilities:{sendReply:false}});
 const host={innerHTML:''};composer.mount(host);
 const buttons=[...host.innerHTML.matchAll(/<button\b[^>]*>/g)].map(x=>x[0]).filter(x=>/data-send(?:\s|-close)/.test(x));
 assert.equal(buttons.length,2);
 for(const button of buttons)assert.doesNotMatch(button,/\bdisabled\b/);
 const events=[];mailbox.subscribe('composer/send',data=>events.push(data));
 host.onclick({target:{closest:selector=>selector==='[data-send]'?{}:null}});
 host.onclick({target:{closest:selector=>selector==='[data-send-close]'?{}:null}});
 assert.equal(events.length,2);
 assert.deepEqual(events.map(e=>e.close),[false,true]);
 composer.update({ticket:{id:'gorgias:1',status:'unknown'},capabilities:{sendReply:false},sendError:ACTIVATE_SEND_MESSAGE});
 assert.match(composer.render(),/role="alert">Activate the send access\./);
});
