import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createCanonicalReviewAdapter} from '../dormant/canonical-review.js';
const context={inboxTicketId:'gorgias:1',sourceMessageId:'m1',draftRevision:'a'.repeat(64),sourceRevision:'b'.repeat(64),contextId:'c'.repeat(64),recipient:'qa@example.com',channel:'email',draftText:'Displayed draft',reviewable:true,sendEnabled:false,sendAndCloseEnabled:false};
test('dormant adapter requests only canonical GET and freezes reviewed text mapping',async()=>{
 const calls=[];
 const adapter=createCanonicalReviewAdapter(async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({ok:true,context})};});
 const loaded=await adapter.load({inboxTicketId:'gorgias:1',sourceMessageId:'m1',draftRevision:context.draftRevision,recipient:'qa@example.com'});
 const snapshot=adapter.snapshotForReview(loaded,'Edited review text');
 assert.equal(calls[0].options.method,'GET');assert.equal(snapshot.displayedDraft,'Displayed draft');
 assert.equal(snapshot.reviewedText,'Edited review text');assert.ok(Object.isFrozen(snapshot));
 assert.equal(adapter.send,undefined);assert.equal(snapshot.sendEnabled,false);
});
test('wrong ticket, stale source or changed recipient cannot produce review snapshot',async()=>{
 const adapter=createCanonicalReviewAdapter(async()=>({ok:true,json:async()=>({ok:true,context:{...context,recipient:'changed@example.com'}})}));
 await assert.rejects(adapter.load({inboxTicketId:'gorgias:01',sourceMessageId:'m1'}),/Invalid/);
 await assert.rejects(adapter.load({inboxTicketId:'gorgias:1',sourceMessageId:'wrong'}),/mismatch/);
 await assert.rejects(adapter.load({inboxTicketId:'gorgias:1',sourceMessageId:'m1',recipient:'qa@example.com'}),/Recipient changed/);
 assert.throws(()=>adapter.snapshotForReview({...context,reviewable:false},'text'),/not ready/);
});
test('adapter is absent from production boot and static serving allowlist',()=>{
 const files=JSON.parse(readFileSync(new URL('../static-manifest.json',import.meta.url),'utf8'));
 assert.ok(!files.some(file=>file.startsWith('dormant/')));
 assert.doesNotMatch(readFileSync(new URL('../js/boot.js',import.meta.url),'utf8'),/canonical-review|dormant/);
});
