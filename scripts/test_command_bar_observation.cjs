// SPDX-License-Identifier: Apache-2.0
// Execute the shipped read-only command bar against bounded synthetic transports.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../static/shared/szl_command_bar.js'), 'utf8');
const transportStart = source.indexOf('  function fetchJson(');
const transportEnd = source.indexOf('  function setChip(', transportStart);
const probeStart = source.indexOf('    var lastHead = null;');
const probeEnd = source.indexOf("    cmdkBtn.addEventListener('click', openPalette);", probeStart);
assert(transportStart >= 0 && transportEnd > transportStart && probeStart >= 0 && probeEnd > probeStart);
function transport(fetch) {
  return vm.runInNewContext(source.slice(transportStart, transportEnd) + '\nfetchJson', {
    fetch, AbortController, TextDecoder, Uint8Array, URL, setTimeout, clearTimeout,
    performance, Date, Promise,
  });
}
const reply = (value, headers = {}) => new Response(JSON.stringify(value), {
  headers: {'content-type':'application/json', ...headers},
});
async function within(promise, limit = 150) {
  let timer;
  try {
    return await Promise.race([
      promise.then(value => ({state:'resolved',value}), error => ({state:'rejected',error})),
      new Promise(resolve => {timer=setTimeout(() => resolve({state:'pending'}), limit);}),
    ]);
  } finally { clearTimeout(timer); }
}

test('fresh JSON preserves zero and false with explicit read-only same-origin options', async () => {
  const calls=[];
  const read=transport(async (url, options) => {calls.push({url,options});return reply({zero:0,no:false});});
  assert.equal(JSON.stringify(await read('/healthz', 1000)), '{"zero":0,"no":false}');
  assert.equal(calls.length,1);
  assert.equal(calls[0].options.method,'GET');
  assert.equal(calls[0].options.mode,'same-origin');
  assert.equal(calls[0].options.redirect,'error');
  assert.equal(calls[0].options.credentials,'same-origin');
  assert.equal(calls[0].options.cache,'no-store');
  assert.equal(calls[0].options.headers.Accept,'application/json');
});

test('body deadline remains active after successful headers and cancels the stream', async () => {
  let cancelled=0, signal;
  const read=transport(async (_, options) => {
    signal=options.signal;
    return new Response(new ReadableStream({cancel(){cancelled++;}}), {headers:{'content-type':'application/json'}});
  });
  const outcome=await within(read('/healthz',20));
  assert.equal(outcome.state,'rejected','a body stall must settle before the external test guard');
  assert.equal(signal.aborted,true);
  assert.equal(cancelled,1);
});

test('headers that never arrive are bounded even when the supplied fetch ignores abort', async () => {
  let calls=0, signal;
  const read=transport((_, options) => {calls++;signal=options.signal;return new Promise(()=>{});});
  const outcome=await within(read('/healthz',20));
  assert.equal(outcome.state,'rejected');
  assert.equal(signal.aborted,true);
  assert.equal(calls,1);
});

for (const contentType of ['text/html','application/json-not-a-media-type']) {
  test('refuses a JSON-looking body under '+contentType, async () => {
    await assert.rejects(transport(async()=>reply({status:'ok'},{'content-type':contentType}))('/healthz',1000));
  });
}

test('refuses a redirected response without painting its payload', async () => {
  const response=reply({status:'ok'});
  Object.defineProperty(response,'redirected',{value:true});
  await assert.rejects(transport(async()=>response)('/healthz',1000));
});

test('rejects invalid UTF-8 rather than silently replacing bytes', async () => {
  const body=new Uint8Array([123,34,120,34,58,34,255,34,125]);
  const read=transport(async()=>new Response(body,{headers:{'content-type':'application/json'}}));
  await assert.rejects(read('/healthz',1000));
});

test('chunked input has a hard one-MiB body bound without trusting Content-Length', async () => {
  await assert.rejects(transport(async()=>reply({x:'x'.repeat(1024*1024)}))('/healthz',1000));
});

test('oversized announced content is refused before reading its body', async () => {
  let reads=0;
  const response={ok:true,redirected:false,headers:new Headers({'content-type':'application/json','content-length':'1048577'}),
    body:{getReader(){reads++;throw Error('must not read');}},json:async()=>({status:'ok'})};
  await assert.rejects(transport(async()=>response)('/healthz',1000));
  assert.equal(reads,0);
});

test('an unbounded response transport is not accepted', async () => {
  const response={ok:true,headers:new Headers({'content-type':'application/json'}),body:null,json:async()=>({status:'ok'})};
  await assert.rejects(transport(async()=>response)('/healthz',1000));
});

test('malformed JSON and HTTP refusal do not retry or expose backend error bodies', async () => {
  for (const response of [new Response('{oops',{headers:{'content-type':'application/json'}}),
    new Response('private-backend-detail',{status:403})]) {
    let calls=0;
    const outcome=await within(transport(async()=>{calls++;return response;})('/healthz',1000));
    assert.equal(outcome.state,'rejected');assert.equal(calls,1);
    assert(!String(outcome.error).includes('private-backend-detail'));
  }
});

test('off-origin and network-path endpoints are rejected before fetch', async () => {
  for (const url of ['https://example.invalid/status','//example.invalid/status','/\\example.invalid/status']) {
    let calls=0;
    const read=transport(async()=>{calls++;return reply({});});
    await assert.rejects(read(url,1000));assert.equal(calls,0);
  }
});

function element() {
  const attrs=new Map(), classes=new Set();
  const label={textContent:''};
  return {textContent:'',title:'',firstChild:{textContent:''},isConnected:true,
    setAttribute:(k,v)=>attrs.set(k,String(v)),getAttribute:k=>attrs.get(k)??null,
    removeAttribute:k=>attrs.delete(k),querySelector:()=>label,label,
    classList:{add:(...xs)=>xs.forEach(x=>classes.add(x)),remove:(...xs)=>xs.forEach(x=>classes.delete(x)),
      contains:x=>classes.has(x),toggle:(x,on)=>on?classes.add(x):classes.delete(x)}};
}
function fixtures(url) {
  if(url==='/healthz')return {status:'ok'};
  if(url==='/api/build-info')return {status:'OBSERVED',build:{revision:'a'.repeat(40)},runtime:{platform:'local-test',python:'fixture'}};
  if(url.endsWith('/honest'))return {locked_formula_count:8};
  if(url.includes('/wow/ledger'))return {chain_depth:0,receipts:[]};
  return {};
}
function probeHarness() {
  const nodes=Object.fromEntries(['root','svc','lam','kern','chain','age','evidencePanel','evidenceRevision','evidenceRuntime','evidenceObserved'].map(x=>[x,element()]));
  const intervals=[],timers=[],events=new Map(),calls=[];
  let clock=Date.parse('2030-01-01T00:00:00Z'), behavior=url=>Promise.resolve(fixtures(url));
  class TestDate extends Date { constructor(...args){super(...(args.length?args:[clock]));} static now(){return clock;} }
  const document={visibilityState:'visible',documentElement:{getAttribute:()=>null},getElementById:()=>null,
    addEventListener:(name,fn)=>events.set(name,fn),removeEventListener:(name,fn)=>{if(events.get(name)===fn)events.delete(name);}};
  const context={...nodes,document,Date:TestDate,performance:{now:()=>clock},Promise,
    setInterval:(fn,ms)=>{const t={fn,ms};intervals.push(t);return t;},clearInterval:t=>{if(t)t.cleared=true;},
    setTimeout:(fn,ms)=>{const t={fn,ms};timers.push(t);return t;},clearTimeout:t=>{if(t)t.cleared=true;},
    fetchJson:(url,ms)=>{calls.push({url,ms});return behavior(url);},
    setChip:(n,live,text)=>{n.live=live;n.label.textContent=text;},roll:(n,text)=>{n.textContent=text;},reduce:true};
  const api=vm.runInNewContext(source.slice(probeStart,probeEnd)+'\n({probe});',context);
  return {nodes,calls,document,timers,intervals,events,api,
    setBehavior:fn=>{behavior=fn;},advance:ms=>{clock+=ms;}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('the existing seven probes remain read-only and preserve a genuinely reported zero',async()=>{
  const h=probeHarness();await settle();assert.equal(h.calls.length,7);
  assert(h.calls.some(c=>c.url.endsWith('/wow/ledger?limit=1&advance=0')));
  assert.equal(h.nodes.chain.label.textContent,'0');
  assert.equal(h.nodes.svc.label.textContent,'ONLINE');
  assert.equal(h.nodes.evidenceRevision.textContent,'OBSERVED / '+ 'a'.repeat(12));
});

test('refresh revokes the previous online view while the next observation is pending',async()=>{
  const h=probeHarness();await settle();assert.equal(h.nodes.svc.live,true);
  h.setBehavior(()=>new Promise(()=>{}));h.api.probe();
  assert.equal(h.nodes.svc.live,false);
  assert.equal(h.nodes.svc.label.textContent,'OBSERVING');
  assert.equal(h.nodes.evidencePanel.getAttribute('data-evidence-state'),'OBSERVING');
});

test('a slow batch coalesces repeated refresh triggers instead of accumulating probes',async()=>{
  const h=probeHarness();await settle();h.calls.length=0;
  h.setBehavior(()=>new Promise(()=>{}));h.api.probe();h.api.probe();h.api.probe();
  assert.equal(h.calls.length,7);
});

test('suspended polling expires old evidence and clears live styling',async()=>{
  const h=probeHarness();await settle();h.advance(31000);
  const expires=h.timers.find(t=>!t.cleared&&t.ms===30000);
  assert(expires,'the observation must have an explicit expiry');expires.fn();
  assert.equal(h.nodes.svc.live,false);
  assert.equal(h.nodes.evidencePanel.getAttribute('data-evidence-state'),'STALE');
});

test('hidden documents make no new probe requests',async()=>{
  const h=probeHarness();await settle();h.calls.length=0;h.document.visibilityState='hidden';h.api.probe();
  assert.equal(h.calls.length,0);
});

test('a response arriving while hidden is not published as a fresh observation',async()=>{
  const h=probeHarness();await settle();const releases=[];
  h.setBehavior(url=>new Promise(resolve=>releases.push(()=>resolve(fixtures(url)))));h.api.probe();
  h.document.visibilityState='hidden';releases.forEach(f=>f());await settle();
  assert.equal(h.nodes.svc.live,false);
});

test('a detached bar stops polling rather than becoming a hidden second reader',async()=>{
  const h=probeHarness();await settle();h.calls.length=0;h.nodes.root.isConnected=false;h.api.probe();
  assert.equal(h.calls.length,0);
  assert(h.intervals.every(t=>t.cleared));
});

test('failed refresh replaces the prior success, with no invented observations',async()=>{
  const h=probeHarness();await settle();h.setBehavior(()=>Promise.reject(new Error('private detail')));
  h.api.probe();await settle();assert.equal(h.nodes.svc.live,false);
  assert.equal(h.nodes.svc.label.textContent,'UNAVAILABLE');
  assert.equal(h.nodes.evidenceRevision.textContent,'UNAVAILABLE');
});
