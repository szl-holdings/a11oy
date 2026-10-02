// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const html = fs.readFileSync(path.join(__dirname, '../web/verify-receipt.html'), 'utf8');
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/i)[1];

class Element {
  constructor() { this.value=''; this.textContent=''; this.innerHTML=''; this.disabled=false; this.listeners={}; this.children=[]; this.classes=new Set(['hide']); this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x)}; }
  addEventListener(type, fn) { this.listeners[type]=fn; }
  fire(type) { return this.listeners[type]?.({target:this}); }
  insertAdjacentHTML(_, value) { this.innerHTML += value; }
  appendChild(child) { this.children.push(child); }
  scrollIntoView() {}
}
function setup(fetcher=()=>Promise.reject(new Error('offline')), search='') {
  const elements=new Map(), timers=new Map(); let timerId=0;
  const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const sandbox={TextEncoder,TextDecoder,Uint8Array,URLSearchParams,AbortController,atob,btoa,
    location:{origin:'http://localhost',search},
    window:{crypto:crypto.webcrypto,location:{origin:'http://localhost',search}},
    document:{getElementById:get,createElement:()=>new Element(),addEventListener(){}},history:{replaceState(){}},navigator:{},fetch:fetcher,
    setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);}};
  vm.runInNewContext(script,sandbox,{timeout:1000});
  return {get,timers,click:id=>get(id).fire('click'),edit:(id,value)=>{get(id).value=value;get(id).fire('input');},
    result:()=>JSON.parse(get('raw').textContent),hidden:()=>get('result').classes.has('hide')};
}
const keyPair=crypto.generateKeyPairSync('ec',{namedCurve:'prime256v1'});
const publicKey=keyPair.publicKey.export({type:'spki',format:'pem'});
function fixture(encoding='ieee-p1363', payload=Buffer.from('{"text":"café Λ","decision":"DENY"}'), payloadType='application/vnd.szl.khipu+json') {
  const type=Buffer.from(payloadType);
  const pae=Buffer.concat([Buffer.from(`DSSEv1 ${type.length} `),type,Buffer.from(` ${payload.length} `),payload]);
  const sig=crypto.sign('sha256',pae,{key:keyPair.privateKey,dsaEncoding:encoding});
  return {payloadType,payload:payload.toString('base64'),signatures:[{keyid:'test-key',sig:sig.toString('base64')}]};
}
function fill(h, envelope=fixture()) { h.get('env').value=JSON.stringify(envelope); h.get('publicKey').value=publicKey; h.get('expectedKeyId').value='test-key'; return envelope; }
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function onlineResult(statuses=['VERIFIED','UNAVAILABLE','UNAVAILABLE'], verdict='PARTIAL') {
  return {ok:true,verdict,checks:['signature','payload_digest','hash_chain'].map((check,i)=>({check,status:statuses[i]}))};
}

for(const encoding of ['ieee-p1363','der']) test(`real ${encoding} DSSE verifies only within supplied-key scope`,async()=>{
  let requests=0; const h=setup(()=>{requests++;throw new Error('network forbidden');}); const env=fill(h,fixture(encoding));
  h.get('expectedDigest').value=crypto.createHash('sha256').update(Buffer.from(env.payload,'base64')).digest('hex');
  await h.click('go'); const result=h.result();
  assert.equal(result.checks[0].status,'VERIFIED'); assert.equal(result.checks[1].status,'VERIFIED');
  assert.equal(result.verdict,'PARTIAL'); assert.equal(result.evidence.authorization,'UNKNOWN');
  assert.equal(result.evidence.signerState,'SIGNED_UNVERIFIED'); assert.equal(result.checks[2].status,'UNAVAILABLE'); assert.equal(requests,0);
});
test('one-byte payload mutation fails signature verification',async()=>{
  const h=setup(), env=fixture(); const bytes=Buffer.from(env.payload,'base64');bytes[2]^=1;env.payload=bytes.toString('base64');fill(h,env);
  await h.click('go'); assert.equal(h.result().verdict,'FAIL'); assert.equal(h.result().checks[0].status,'MISMATCH');
});
test('PAE uses UTF-8 byte lengths for a non-ASCII payload type',async()=>{
  const h=setup();fill(h,fixture('der',Buffer.from('exact bytes'),'application/example;name=Λ'));await h.click('go');
  assert.equal(h.result().checks[0].status,'VERIFIED');assert.equal(h.result().verdict,'PARTIAL');
});
test('matching key id cannot make a signature pass under a different public key',async()=>{
  const h=setup();fill(h);const wrong=crypto.generateKeyPairSync('ec',{namedCurve:'prime256v1'});
  h.get('publicKey').value=wrong.publicKey.export({type:'spki',format:'pem'});await h.click('go');
  assert.equal(h.result().checks[0].status,'MISMATCH');assert.equal(h.result().verdict,'FAIL');
});
test('independent digest mismatch overrides a valid signature',async()=>{
  const h=setup();fill(h);h.get('expectedDigest').value='0'.repeat(64);await h.click('go');assert.equal(h.result().verdict,'FAIL');
});
test('URL-safe payload/signature and share encoding verify exact bytes',async()=>{
  const h=setup(), env=fixture();env.payload=Buffer.from(env.payload,'base64').toString('base64url');env.signatures[0].sig=Buffer.from(env.signatures[0].sig,'base64').toString('base64url');fill(h,env);
  h.get('env').value=Buffer.from(JSON.stringify(env)).toString('base64url');await h.click('go');assert.equal(h.result().checks[0].status,'VERIFIED');
});
test('missing signature is unsigned even with a supplied key',async()=>{
  const h=setup(), env=fixture();env.signatures=[];fill(h,env);await h.click('go');assert.equal(h.result().evidence.signerState,'UNSIGNED');assert.equal(h.result().verdict,'INCONCLUSIVE');
});

for (const kind of ['verified signature', 'unsigned envelope', 'missing public key']) {
  test(`local ${kind} is reported evidence without a live measurement claim`, async () => {
    const h = setup(), env = fixture();
    if (kind === 'unsigned envelope') env.signatures = [];
    fill(h, env);
    if (kind === 'missing public key') h.get('publicKey').value = '';
    await h.click('go');
    const result = h.result();
    const expected = {
      'verified signature': 'VERIFIED',
      'unsigned envelope': 'UNSIGNED-LOCAL',
      'missing public key': 'UNAVAILABLE'
    };
    assert.equal(result.checks[0].status, expected[kind]);
    assert.equal(result.evidence.evidenceClass, 'REPORTED');
    assert.equal(result.evidence.runtimeState, 'NOT_PROBED');
    assert.equal(result.evidence.authorization, 'UNKNOWN');
    assert.match(result.evidence.bound, /Does not establish trusted signer identity/);
  });
}
for(const kind of ['missing type','missing signatures','duplicate key','wrong key','oversize','bad base64','private pem']) test(`${kind} cannot preserve a prior verification`,async()=>{
  const h=setup();fill(h);await h.click('go');assert.equal(h.result().checks[0].status,'VERIFIED');let env=fixture();
  if(kind==='missing type')delete env.payloadType;
  if(kind==='missing signatures')delete env.signatures;
  if(kind==='duplicate key')env.signatures.push(env.signatures[0]);
  if(kind==='wrong key')env.signatures[0].keyid='other';
  if(kind==='bad base64')env.payload='%%%';
  fill(h,env);if(kind==='oversize')h.get('env').value='x'.repeat(262145);
  if(kind==='private pem')h.get('publicKey').value=keyPair.privateKey.export({type:'pkcs8',format:'pem'});
  await h.click('go');assert.equal(h.hidden(),true);assert.match(h.get('status').textContent,/UNAVAILABLE/);assert.equal(h.get('go').disabled,false);
});
test('clear and input edits invalidate even an uncancellable late response',async()=>{
  for(const action of ['clear','edit']){
    let respond;const h=setup(()=>new Promise(r=>respond=r));fill(h);const running=h.click('goOnline');
    if(action==='clear')h.click('clear');else h.edit('env','different input');
    respond({ok:true,json:async()=>onlineResult()});await running;assert.equal(h.hidden(),true);assert.equal(h.get('raw').textContent,'');
  }
});
test('older response cannot overwrite newer verification',async()=>{
  const responses=[];const h=setup(()=>new Promise(r=>responses.push(r)));fill(h);const older=h.click('goOnline');h.edit('rid','new');const newer=h.click('goOnline');
  responses[1]({ok:true,json:async()=>onlineResult(['MISMATCH','UNAVAILABLE','UNAVAILABLE'],'FAIL')});await newer;
  responses[0]({ok:true,json:async()=>onlineResult()});await older;assert.equal(h.result().verdict,'FAIL');
});
test('deadline includes a stalled response body and late success stays hidden',async()=>{
  let body;const h=setup(async()=>({ok:true,json:()=>new Promise(r=>body=r)}));fill(h);const running=h.click('goOnline');await tick();
  [...h.timers.values()][0]();await running;assert.equal(h.hidden(),true);assert.match(h.get('status').textContent,/timed out/);
  body(onlineResult());await tick();assert.equal(h.hidden(),true);assert.equal(h.timers.size,0);
});
test('HTTP errors, malformed checks, and inconsistent PASS all fail closed',async()=>{
  for(const response of [{ok:false,status:503,json:async()=>onlineResult()},
    {ok:true,json:async()=>({ok:true,verdict:'PASS',checks:[]})},
    {ok:true,json:async()=>onlineResult(['VERIFIED','UNAVAILABLE','UNAVAILABLE'],'PASS')}]){
    const h=setup(async()=>response);fill(h);await h.click('goOnline');assert.equal(h.hidden(),true);assert.match(h.get('status').textContent,/UNAVAILABLE/);
  }
});
test('query links populate input without transmitting it',()=>{
  let calls=0;const h=setup(()=>{calls++;},'?receipt=abc123');assert.equal(h.get('rid').value,'abc123');assert.equal(calls,0);
});


test('preserved math demonstration distinguishes hidden weak from false friend at policy 0.80',()=>{
  const h=setup();const rows=h.get('demoBody').children;
  assert.equal(rows.length,5);assert.match(rows[3].innerHTML,/hidden_weak/);assert.equal(rows[3].className,'dang');
  assert.match(rows[4].innerHTML,/false_friend/);assert.equal(rows[4].className,'admit');
  assert.match(h.get('liar70').textContent,/0.70.*POLICY 0.80/);
});
for(const action of ['loadAxes','loadFriend','loadLambda','tamper']) test(`demo control ${action} invalidates old results and pending work`,async()=>{
  let respond,requests=0;const h=setup(()=>{requests++;return new Promise(r=>respond=r);});fill(h);
  await h.click('go');assert.equal(h.hidden(),false);h.click(action);assert.equal(h.hidden(),true);assert.equal(requests,0);
  fill(h);const pending=h.click('goOnline');h.click(action);
  respond({ok:true,json:async()=>onlineResult()});await pending;assert.equal(h.hidden(),true);assert.equal(requests,1);
  assert.equal(h.get('go').disabled,false);
});
test('tamper control changes exactly one decoded byte without replacing its signature',()=>{
  const h=setup(),env=fill(h);h.click('tamper');const changed=JSON.parse(h.get('env').value);
  const before=Buffer.from(env.payload,'base64'),after=Buffer.from(changed.payload,'base64');
  assert.equal(before.length,after.length);assert.equal(before.filter((b,i)=>b!==after[i]).length,1);
  assert.deepEqual(changed.signatures,env.signatures);
});

for (const kind of ['trailing DER', 'negative DER scalar', 'noncanonical base64', 'payload byte bound', 'envelope UTF8 bound', 'signature count']) {
  test(`parser rejects ${kind} without preserving a prior verdict`, async () => {
    const h = setup();
    fill(h);
    await h.click('go');
    assert.equal(h.result().checks[0].status, 'VERIFIED');
    const env = fixture('der');
    const expected = {
      'trailing DER': /Unsupported P-256 signature encoding/,
      'negative DER scalar': /Invalid DER scalar/,
      'noncanonical base64': /Noncanonical or oversized base64 input/,
      'payload byte bound': /Noncanonical or oversized base64 input/,
      'envelope UTF8 bound': /Envelope exceeds 256 KiB/,
      'signature count': /up to 16 signatures/
    };
    if (kind === 'trailing DER') {
      const bytes = Buffer.from(env.signatures[0].sig, 'base64');
      env.signatures[0].sig = Buffer.concat([bytes, Buffer.from([0])]).toString('base64');
    }
    if (kind === 'negative DER scalar') {
      const bytes = Buffer.from(env.signatures[0].sig, 'base64');
      bytes[4] |= 0x80;
      env.signatures[0].sig = bytes.toString('base64');
    }
    if (kind === 'noncanonical base64') env.payload = 'Zh==';
    if (kind === 'payload byte bound') env.payload = Buffer.alloc(131073).toString('base64');
    if (kind === 'signature count') env.signatures = Array(17).fill(env.signatures[0]);
    fill(h, env);
    if (kind === 'envelope UTF8 bound') h.get('env').value = 'é'.repeat(131073);
    await h.click('go');
    assert.equal(h.hidden(), true);
    assert.equal(h.get('raw').textContent, '');
    assert.match(h.get('status').textContent, expected[kind]);
    assert.equal(h.get('go').disabled, false);
  });
}

test('offline DSSE verifies arbitrary binary payload bytes without JSON reinterpretation', async () => {
  let requests = 0;
  const h = setup(() => { requests++; throw new Error('network forbidden'); });
  fill(h, fixture('der', Buffer.from([0xff, 0x00, 0x80, 0x7f])));
  await h.click('go');
  const result = h.result();
  assert.equal(result.checks[0].status, 'VERIFIED');
  assert.equal(result.verdict, 'PARTIAL');
  assert.equal(result.checks[1].status, 'UNAVAILABLE');
  assert.equal(result.checks[2].status, 'UNAVAILABLE');
  assert.equal(result.evidence.authorization, 'UNKNOWN');
  assert.equal(requests, 0);
});
