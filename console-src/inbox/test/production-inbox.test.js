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
