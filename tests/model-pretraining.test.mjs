/* Source-only tests. These fixtures do not assert any model was trained. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source = await readFile(new URL('../pages/model-pretraining.js', import.meta.url),'utf8');
const {validate,filterRows,safeSource} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
function fixture() {
  return {schema:'szl.model-pretraining-view/v1',available:true,state:'PRETRAINING_REVIEW_NOT_ALIGNMENT',
    trainingAllowed:false,sourceAlignmentVerified:false,wholeOrganizationInventoryVerified:false,
    inventoryScope:{visibility:'public-only',authenticated:false,privateAssetsIncluded:false},
    authority:{training:false,inference:false,publication:false,promotion:false,deletion:false,toolExecution:false},
    returned:1,sourcePointersDeclared:0,manifestSha256:'a'.repeat(64),observedAt:'2026-09-10T03:20:41Z',
    snapshotFreshness:'STALE_SNAPSHOT',bounds:['Snapshot, not a live or trained model.'],categoryCounts:{ADAPTER_HINT:1},
    models:[{id:'SZLHOLDINGS/sample',hubRevision:'a'.repeat(40),categoryHint:'ADAPTER_HINT',
      categoryIsVerified:false,sourceState:'NOT_RESOLVED_BY_THIS_CATALOG',sourceUrl:null,
      hubRevisionState:'RECORDED_SNAPSHOT_NOT_LIVE',nextAction:'Verify source and bytes.',gated:false,disabled:false,
      weightsVerified:false,sourceBytesVerified:false,evaluationVerified:false,publicationVerified:false,
      runtimeVerified:false,trainingAllowed:false}]};
}
test('valid snapshot does not assert training or alignment',()=>assert.equal(validate(fixture()).trainingAllowed,false));
for (const key of ['trainingAllowed','sourceAlignmentVerified','wholeOrganizationInventoryVerified']) {
  test(`reject unsupported ${key}`,()=>{const v=fixture();v[key]=true;assert.throws(()=>validate(v));});
}
for (const key of ['training','inference','publication','promotion','deletion','toolExecution']) {
  test(`reject ${key} authority`,()=>{const v=fixture();v.authority[key]=true;assert.throws(()=>validate(v));});
}
test('reject unknown additional authority',()=>{const v=fixture();v.authority.execute=true;assert.throws(()=>validate(v));});
for (const key of ['weightsVerified','sourceBytesVerified','evaluationVerified','publicationVerified','runtimeVerified','trainingAllowed']) {
  test(`reject row ${key}`,()=>{const v=fixture();v.models[0][key]=true;assert.throws(()=>validate(v));});
}
test('reject count mismatch',()=>{const v=fixture();v.returned=2;assert.throws(()=>validate(v));});
test('reject duplicate repository rows',()=>{const v=fixture();v.models.push({...v.models[0]});v.returned=2;v.categoryCounts.ADAPTER_HINT=2;assert.throws(()=>validate(v));});
test('reject invalid SHA and arbitrary ID',()=>{for(const patch of [{hubRevision:'main'},{id:'evil/site'},{id:'SZLHOLDINGS/../x'}]){const v=fixture();Object.assign(v.models[0],patch);assert.throws(()=>validate(v));}});
test('unavailable API is not a valid zero-sized snapshot',()=>assert.throws(()=>validate({schema:'szl.model-pretraining-view/v1',available:false,models:[],returned:null})));
test('empty observed snapshot stays unqualified',()=>{const v=fixture();v.models=[];v.returned=0;v.categoryCounts={};assert.equal(validate(v).returned,0);});
test('incorrect category count rejected',()=>{const v=fixture();v.categoryCounts.ADAPTER_HINT=2;assert.throws(()=>validate(v));});
test('incorrect source count rejected',()=>{const v=fixture();v.sourcePointersDeclared=1;assert.throws(()=>validate(v));});
test('source link does not prove source parity',()=>{const v=fixture();v.models[0].sourceState='DECLARED_POINTER_ONLY';v.models[0].sourceUrl='https://github.com/szl-holdings/szl-forge';v.sourcePointersDeclared=1;assert.equal(validate(v).sourceAlignmentVerified,false);});
test('scope must remain public-only',()=>{const v=fixture();v.inventoryScope.privateAssetsIncluded=true;assert.throws(()=>validate(v));});
test('naive and invalid dates rejected',()=>{for(const date of ['2026-09-10T03:20:41','invalid']){const v=fixture();v.observedAt=date;assert.throws(()=>validate(v));}});
test('false LIVE freshness rejected',()=>{const v=fixture();v.snapshotFreshness='LIVE';assert.throws(()=>validate(v));});
test('search and category conjunction',()=>{const rows=fixture().models;assert.equal(filterRows(rows,'SAMPLE','ADAPTER_HINT').length,1);assert.equal(filterRows(rows,'SAMPLE','GGUF_HINT').length,0);assert.equal(filterRows(rows,'none','ALL').length,0);});
test('links must be declared SZL GitHub sources',()=>{assert.equal(safeSource('https://github.com/szl-holdings/szl-forge/tree/main/khipu'),'https://github.com/szl-holdings/szl-forge/tree/main/khipu');});
for(const url of ['javascript:alert(1)','https://github.com.evil/szl-holdings/a','https://github.com/other/a',
  'https://u@github.com/szl-holdings/a','https://github.com/szl-holdings/a/../b',
  'https://github.com/szl-holdings/a/%2e%2e/b','https://github.com/szl-holdings/a?token=x',
  '\nhttps://github.com/szl-holdings/a','https://github.com/szl-holdings/a\\b']) {
  test(`unsafe link rejected ${JSON.stringify(url)}`,()=>assert.equal(safeSource(url),null));
}
