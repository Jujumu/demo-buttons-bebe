import test from 'node:test';
import assert from 'node:assert/strict';
import {safeWebUrl} from '../js/util.js';
import {createThreadTissue} from '../js/tissues/thread.js';
test('executable and credential-bearing URLs cannot become links',()=>{
 for(const value of ['javascript:alert(1)','data:text/html,x','//evil.example','https://user:pass@example.com','java\nscript:alert(1)','file:///etc/passwd'])assert.equal(safeWebUrl(value),'');
 assert.equal(safeWebUrl('https://carrier.example/track?id=1'),'https://carrier.example/track?id=1');
});
test('unsafe attachment URLs are omitted rather than only escaped',()=>{
 const tissue=createThreadTissue({mailbox:{}});
 const html=tissue.render({ticket:{id:'t',messages:[{id:'m',body:'hello',attachments:[{url:'javascript:alert(1)'}]}],statusEvents:[]}});
 assert.doesNotMatch(html,/javascript:|data-attach-open/);
});
import {renderOrder} from '../js/tissues/order.js';
test('tracking and invoice renderers omit executable hyperlinks',()=>{
 const html=renderOrder({ok:true,record:{lineItems:{nodes:[]}},hasTracking:true,tracking:{url:'javascript:alert(1)'},invoiceUrl:'javascript:alert(2)'});
 assert.doesNotMatch(html,/href="javascript:/);
});
