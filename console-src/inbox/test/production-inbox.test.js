import test from 'node:test';
import assert from 'node:assert/strict';
import {createInboxOrgan} from '../js/inbox.js';
import {createHelpdeskShop} from '../js/shop/production-shop.js';

test('empty production responses do not become demo tickets', async () => {
 const shop=createHelpdeskShop({client:{invoke:async tool => ({ok:true,source:'inbox',tickets:[],gorgiasEnabled:false,outboundEnabled:false})}});
 const result=await createInboxOrgan({shop,viewId:'all'}).ready();
 assert.equal(result.selectedId,null);
 assert.match(result.html,/No tickets yet/);
 assert.doesNotMatch(result.html,/Ada Demo|Casey Sandbox|Sample Romper/);
});
test('HTTP failures show unavailable state without fixture fallback', async () => {
 const shop=createHelpdeskShop({client:{invoke:async () => {throw new Error('offline');}}});
 const result=await createInboxOrgan({shop,viewId:'all'}).ready();
 assert.equal(result.selectedId,null);
 assert.match(result.html,/Tickets unavailable/);
 assert.doesNotMatch(result.html,/Ada Demo|Casey Sandbox/);
});
test('production client rejects a stale fixture response', async () => {
 const shop=createHelpdeskShop({client:{invoke:async () => ({ok:true,source:'sample',tickets:[{id:'t-ada-track'}]})}});
 await assert.rejects(shop.listTickets({}),/Preview data/);
});

const localTicket = {id:'t-in-test',customerName:'Local test',subject:'Privacy request',snippet:'Test',status:'open',updatedAt:'2026-09-07T00:00:00Z',messages:[],statusEvents:[],requestType:'privacy_request'};

test('failed mutations never fabricate a completed workflow', async () => {
  for (const [method, action] of [['escalateTicket','escalate'],['markPrivacyHandled','markPrivacyHandled'],['markUnsubscribed','markUnsubscribed'],['markBugHandled','markBugHandled']]) {
    const shop = {[method]:async () => {throw new Error('Persistence failed');}};
    const organ = createInboxOrgan({shop,tickets:[localTicket],viewId:'all'});
    await organ.ready();
    await assert.rejects(organ[action](), /Persistence failed/);
    assert.doesNotMatch(organ.snapshot().html,/data-escalated|thread-request-handled/);
  }
});

test('missing or failed capability response leaves unsupported controls hidden', async () => {
  const shop = createHelpdeskShop({client:{invoke:async tool => {
    if (tool === 'helpdesk.capabilities') throw new Error('offline');
    return {ok:true,source:'inbox',tickets:[localTicket],ticket:localTicket};
  }}});
  const organ = createInboxOrgan({shop,viewId:'all'});
  const result = await organ.ready();
  assert.doesNotMatch(result.html,/data-escalate=|data-summarize=|data-macros\b|data-privacy-gate-open/);
  assert.match(result.html,/Customer and order lookup is not connected/);
  await assert.rejects(organ.escalate(),/not available/);
  assert.equal(organ.attemptSend().sendError,'Activate the send access.');
});
