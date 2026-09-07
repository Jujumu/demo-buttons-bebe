import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const source=html.slice(html.indexOf('function actionStorageKey('),html.indexOf('function actionMessage('));
function browser(storage=new Map()){
 const context=vm.createContext({crypto:webcrypto,TextEncoder,Uint8Array,localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)}});
 vm.runInContext(source,context);return {context,storage};
}
const ticket={ticket_id:1,message_id:'source',draft_text:'draft'};
test('same action keeps its operation id after simulated reload; storage excludes customer text',async()=>{
 const first=browser();const id=await first.context.actionOperation(ticket,'send','private customer reply',false);
 const reloaded=browser(first.storage);
 assert.equal(await reloaded.context.actionOperation(ticket,'send','private customer reply',false),id);
 assert.ok(!JSON.stringify([...first.storage]).includes('private customer reply'));
});
test('unresolved action cannot be replaced with different text',async()=>{
 const {context}=browser();await context.actionOperation(ticket,'send','reply one',false);
 await assert.rejects(context.actionOperation(ticket,'send','reply two',false),/previous action is unresolved/);
});
test('confirmed outcome permits intentional distinct followup while identical retry stays stable',async()=>{
 const {context}=browser();const id=await context.actionOperation(ticket,'send','reply one',false);
 context.rememberAction(ticket,'send',{operation_id:id,delivery_status:'sent'});
 assert.equal(await context.actionOperation(ticket,'send','reply one',false),id);
 assert.notEqual(await context.actionOperation(ticket,'send','reply two',false),id);
});
test('new customer source is a distinct action and new approval defaults off',async()=>{
 const {context}=browser();const id=await context.actionOperation(ticket,'send','reply',false);
 assert.notEqual(await context.actionOperation({...ticket,message_id:'next'},'send','reply',false),id);
 assert.match(html,/let actLearn=false/);
 assert.match(html,/source_message_id:String\(t.message_id\)/);
});

test('uncertain owner alerts remain visible without a retry control',()=>{
 const start=html.indexOf('function ownerAlertWarning('),end=html.indexOf('function overview(){',start);
 const context=vm.createContext({});vm.runInContext(html.slice(start,end),context);
 assert.match(context.ownerAlertWarning(2),/2 owner alerts need review/);
 assert.equal(context.ownerAlertWarning(0),'');
 assert.match(html,/ownerAlertWarning\(stats.owner_alerts_need_attention\)/);
 assert.match(html,/t.owner_alert_status==="uncertain"/);
});

test('switching tickets during operation preparation never changes approved send text',async()=>{
 const body=html.slice(html.indexOf('async function submitAction('),html.indexOf('async function sendReply('));
 let captured;
 const t={ticket_id:1,message_id:'first',customer_email:'one@example.com'};
 const context=vm.createContext({actBusy:false,actDraft:'Approved for first customer',actLearn:false,actSourceDraft:'',actEditorKey:'first',actGeneration:1,
  captureAct(){},curTk:()=>t,keyOf:x=>x.message_id,isEsc:()=>false,confirm:()=>true,render(){},API:'/console/api',
  async actionOperation(){context.actDraft='Different customer draft';return 'operation';},
  async fetch(url,opts){captured=JSON.parse(opts.body);return {async json(){return {delivery_status:'sent'};}};},
  hashActionText:async()=>"revision",rememberAction(){},actionMessage:()=> 'Sent'});
 vm.runInContext(body,context);await context.submitAction('send');
 assert.equal(captured.text,'Approved for first customer');assert.equal(captured.source_message_id,'first');
});

test('a refreshed server draft cannot bless text loaded from an older revision',async()=>{
 const body=html.slice(html.indexOf('async function submitAction('),html.indexOf('async function sendReply('));
 let calls=0;
 const t={ticket_id:1,message_id:'first',draft_text:'new server draft'};
 const context=vm.createContext({actBusy:false,actDraft:'old edited draft',actSourceDraft:'old server draft',actEditorKey:'first',actGeneration:1,
 captureAct(){},curTk:()=>t,keyOf:x=>x.message_id,render(){},fetch(){calls++;}});
 vm.runInContext(body,context);await context.submitAction('send');
 assert.equal(calls,0);assert.match(context.actMsg,/source draft changed/);
});
test('status completion cannot overwrite a newly opened editor',async()=>{
 const body=html.slice(html.indexOf('async function checkActionStatus('),html.indexOf('async function rewriteDraft('));
 let current={ticket_id:1,message_id:'first'};
 const context=vm.createContext({actBusy:false,actGeneration:1,actMsg:'',captureAct(){},curTk:()=>current,keyOf:x=>x.message_id,render(){},API:'/api',
 localStorage:{getItem:()=>JSON.stringify({operation_id:'operation'})},actionStorageKey:()=>'',rememberAction(){},actionMessage:()=> 'old outcome',
 async fetch(){context.actGeneration=2;context.actMsg='new editor';current={ticket_id:2,message_id:'second'};return {json:async()=>({delivery_status:'sent'})};}});
 vm.runInContext(body,context);await context.checkActionStatus();assert.equal(context.actMsg,'new editor');
});
test('overview navigation initializes the requested ticket editor',()=>{
 const source=html.slice(html.indexOf('function goTickets('),html.indexOf('\nfunction render(){'));
 let opened;
 const context=vm.createContext({openTicket:key=>{opened=key;},render(){}});
 vm.runInContext(source,context);context.goTickets('all','customer-message-2');
 assert.equal(opened,'customer-message-2');
});
test('explicit preflight refusal releases local retry block; unknown transport does not',async()=>{
 const {context}=browser();const id=await context.actionOperation(ticket,'send','first',false);
 context.rememberAction(ticket,'send',{error:'invalid_reply'});
 await assert.rejects(context.actionOperation(ticket,'send','fixed',false),/unresolved/);
 context.rememberAction(ticket,'send',{delivery_status:'not_attempted',error:'draft_changed_refresh_ticket'});
 assert.notEqual(await context.actionOperation(ticket,'send','fixed',false),id);
});
