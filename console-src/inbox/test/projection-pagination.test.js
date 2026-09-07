import test from 'node:test';
import assert from 'node:assert/strict';
import {readObservedTickets} from '../js/inbox.js';
const page = prefix => Array.from({length:100},(_,i)=>({id:`${prefix}:${i}`}));
test('generation swap restarts at zero without mixing pages',async()=>{
 const offsets=[];let n=0;
 const shop={listTickets:async ({offset})=>{offsets.push(offset);n++;shop.projection={generatedAt:n===1?'old':'new'};return n===1?page('old'):n===2?page('discard'):n===3?page('new'):[{id:'new:last'}];}};
 const rows=await readObservedTickets(shop);
 assert.deepEqual(offsets,[0,100,0,100]);assert.equal(rows.length,101);
 assert.ok(rows.every(row=>row.id.startsWith('new:')));
});
test('repeated generation swaps are bounded to one restart',async()=>{
 let n=0;const shop={listTickets:async()=>{shop.projection={generatedAt:String(++n)};return page('x');}};
 await assert.rejects(readObservedTickets(shop),/repeatedly/);assert.equal(n,4);
});
test('API failures are not retried or turned into partial success',async()=>{
 let n=0;const shop={listTickets:async()=>{if(++n===2)throw new Error('API unavailable');shop.projection={generatedAt:'same'};return page('x');}};
 await assert.rejects(readObservedTickets(shop),/API unavailable/);assert.equal(n,2);
});
