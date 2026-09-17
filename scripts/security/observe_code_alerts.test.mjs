// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {createDecipheriv, privateDecrypt, constants, generateKeyPairSync} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {collect,publicSummary,seal,githubRead,REPOSITORY} from './observe_code_alerts.mjs';
const revision='a'.repeat(40), prefix=`/repos/${REPOSITORY}`;
function alert(number=1,severity='critical') {return {number,state:'open',url:`https://api.github.com${prefix}/code-scanning/alerts/${number}`,rule:{security_severity_level:severity},most_recent_instance:{location:{path:'SYNTHETIC_PRIVATE_PATH.py'}}};}
function reader(rows=[]) {return async path=>{
 if(path===prefix)return {full_name:REPOSITORY,private:false,default_branch:'main'};
 if(path.endsWith('/git/ref/heads/main'))return {object:{sha:revision}};
 if(path.includes('/instances?'))return [];
 if(path.includes('/code-scanning/alerts?'))return path.includes('page=1&')?rows:[];
 throw new Error('UNEXPECTED_TEST_PATH');
};}
test('complete empty reads are observed, not a security clearance',async()=>{const r=await collect(reader());assert.equal(r.complete,true);assert.equal(publicSummary(r,{}).security_clearance,false);});
test('high priority instances read; private paths absent from summary',async()=>{const r=await collect(reader([alert()]));assert.equal(r.complete,true);assert.equal(r.high_priority_instances.length,1);assert.equal(JSON.stringify(publicSummary(r,{})).includes('SYNTHETIC_PRIVATE'),false);});
test('invalid/partial collections never become zero',async()=>{for(const rows of [null,{},[null],[alert(),alert()]]){const r=await collect(reader(rows));assert.equal(r.complete,false);assert.equal(publicSummary(r,{}).alert_count,null);}});
test('incomplete collection sanitizes error content',async()=>{const r=await collect(async()=>{throw new Error('SYNTHETIC credential secret=x');});assert.equal(r.error_code,'OBSERVATION_FAILED');assert.equal(JSON.stringify(publicSummary(r,{})).includes('secret=x'),false);});
test('different repository or private scope refused',async()=>{for(const privateFlag of [true,null]){const r=await collect(async()=>({full_name:REPOSITORY,private:privateFlag,default_branch:'main'}));assert.equal(r.error_code,'REPOSITORY_IDENTITY');}});
test('moving main cannot qualify stable snapshot',async()=>{let n=0;const base=reader();const r=await collect(async p=>p.endsWith('/git/ref/heads/main')?{object:{sha:(n++?'b':'a').repeat(40)}}:base(p));assert.equal(r.error_code,'DEFAULT_SOURCE_MOVED');});
test('transport fixed origin GET, no redirects, authorization only in header',async()=>{let called=0;await githubRead(prefix,'SYNTHETIC_TOKEN',async(url,opts)=>{called++;assert.equal(url.origin,'https://api.github.com');assert.equal(opts.redirect,'error');assert.equal(opts.method,'GET');assert.equal(url.href.includes('SYNTHETIC_TOKEN'),false);return new Response('{}',{status:200});});assert.equal(called,1);});
test('transport refuses destination and oversized/error bodies',async()=>{await assert.rejects(githubRead('https://evil.invalid','x'),/DESTINATION/);await assert.rejects(githubRead(prefix,'x',async()=>new Response('{}',{status:403})),/READ_HTTP_403/);await assert.rejects(githubRead(prefix,'x',async()=>new Response('{}',{headers:{'content-length':'9000000'}})),/RESPONSE_BOUND/);});
test('recipient substitution refused',()=>{const {publicKey}=generateKeyPairSync('rsa',{modulusLength:2048,publicKeyEncoding:{type:'spki',format:'pem'},privateKeyEncoding:{type:'pkcs8',format:'pem'}});assert.throws(()=>seal({},publicKey,{}),/RECIPIENT_MISMATCH/);});
test('ciphertext contains no plaintext fixture',()=>{const recipient=readFileSync(new URL('./audit-recipient.pem',import.meta.url),'utf8');const e=seal({private:'SYNTHETIC_PRIVATE_PATH.py'},recipient,{repository:REPOSITORY});assert.equal(JSON.stringify(e).includes('SYNTHETIC_PRIVATE_PATH'),false);assert.equal(Buffer.from(e.tag,'base64').length,16);});
