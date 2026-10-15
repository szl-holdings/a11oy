// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Exact local source and assets; provider failures are explicit synthetic fixtures.
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { createServer } = require('node:http');
const { readFileSync, mkdirSync, mkdtempSync, writeFileSync, existsSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { spawnSync } = require('node:child_process');
const { chromium } = require('playwright');

const root = resolve(__dirname, '..');
const output = process.env.LANDING_EVIDENCE_DIR
  ? resolve(process.env.LANDING_EVIDENCE_DIR)
  : mkdtempSync(join(tmpdir(), 'szl-landing-browser-evidence-'));
const base = process.env.LANDING_BASE_SHA || '';
if (base) assert.match(base, /^[0-9a-f]{40}$/);
const assetPaths = new Map([
  ...['szl-flow.css', 'apex-v2.css', 'szl-holo-v2.css', 'szl-spectral-v2.css',
    'szl-flow.js', 'szl-holo-v2.js', 'a11oy-homepage.css'].map(name => [`/assets/${name}`, `console/assets/${name}`]),
  ['/assets/szl/szl-design-system.css', 'console/assets/szl/szl-design-system.css'],
  ['/assets/szl/orbit-v2/szl-icon-32.svg', 'console/assets/szl/orbit-v2/szl-icon-32.svg'],
  ['/social-preview-v5.svg', 'console/social-preview-v5.svg'],
  ['/static/landing-honest-bind.js', 'static/landing-honest-bind.js'],
]);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
function readAt(path, revision) {
  if (!revision) return existsSync(resolve(root, path)) ? readFileSync(resolve(root, path)) : null;
  const r = spawnSync('git', ['show', `${revision}:${path}`], {cwd:root, maxBuffer:8*1024*1024});
  return r.status === 0 ? r.stdout : null;
}
function bundle(revision) {
  return {html:readAt('a11oy_landing.html', revision), files:new Map([...assetPaths].map(([url,path]) => [url,readAt(path,revision)]))};
}
const candidate = bundle('');
assert.ok(candidate.html);
const baseline = base ? bundle(base) : null;
const results = [];
const observations = [];
function check(name, ok, detail = null) { results.push({name, ok:Boolean(ok), detail}); }

// Computed text pairs are a focused contrast check, not a WCAG conformance claim.
async function inspect(page, {contrast = true, targets = true} = {}) {
  return page.evaluate(({contrast,targets}) => {
    const viewport = innerWidth;
    const overflowingText = [], contrastFailures = [], targetFailures = [];
    const context = document.createElement('canvas').getContext('2d', {willReadFrequently:true});
    context.canvas.width=1; context.canvas.height=1;
    const colorCache=new Map(),groundCache=new WeakMap(),styleCache=new WeakMap();
    function style(el) {if(!styleCache.has(el))styleCache.set(el,getComputedStyle(el));return styleCache.get(el);}
    function rgba(color) {if(!colorCache.has(color)){context.clearRect(0,0,1,1);context.fillStyle=color;context.fillRect(0,0,1,1);colorCache.set(color,[...context.getImageData(0,0,1,1).data].map((x,i)=>i===3?x/255:x));}return colorCache.get(color);}
    function over(f,b) { const a=f[3]+b[3]*(1-f[3]);return [0,1,2].map(i=>a?(f[i]*f[3]+b[i]*b[3]*(1-f[3]))/a:0).concat(a); }
    function ground(el) {if(!groundCache.has(el))groundCache.set(el,over(rgba(style(el).backgroundColor),el.parentElement?ground(el.parentElement):[255,255,255,1]));return groundCache.get(el);}
    function luminance(c) {return c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);}
    function visible(el) {return el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) && !el.closest('[hidden],[aria-hidden="true"]');}
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;let lowestContrast=Infinity,textNodes=0;
    while((node=walker.nextNode())) {
      const el=node.parentElement;
      if(!node.textContent.trim() || !el || el.closest('script,style,svg,.skip-link') || !visible(el))continue;
      const range=document.createRange();range.selectNodeContents(node);
      const rect=range.getBoundingClientRect();if(!rect.width||!rect.height)continue;
      textNodes++;
      if(rect.left < -2 || rect.right > viewport+2)overflowingText.push({text:node.textContent.trim().slice(0,90),class:el.className,box:rect.toJSON()});
      if(contrast) {
        const s=style(el), b=ground(el), f=over(rgba(s.color),b);
        const [a,z]=[luminance(f),luminance(b)].sort((a,b)=>b-a),ratio=(a+.05)/(z+.05);
        const large=parseFloat(s.fontSize)>=24 || (parseFloat(s.fontSize)>=18.666 && parseFloat(s.fontWeight)>=700);
        lowestContrast=Math.min(lowestContrast,ratio);
        if(ratio+.005 < (large?3:4.5))contrastFailures.push({text:node.textContent.trim().slice(0,100),class:el.className,ratio,threshold:large?3:4.5,color:s.color,background:b});
      }
    }
    if(targets)for(const el of document.querySelectorAll('a,button,summary')) {
      if(!visible(el)||el.closest('.skip-link'))continue;
      const b=el.getBoundingClientRect();
      if(b.width<43.9||b.height<43.9)targetFailures.push({text:el.textContent.trim().slice(0,90),width:b.width,height:b.height});
    }
    const menu=document.querySelector('#menu-toggle'),sub=document.querySelector('header.nav .brand .sub');
    return {viewport,scrollWidth:document.documentElement.scrollWidth,bodyOverflow:getComputedStyle(document.body).overflowX,
      archiveOpen:document.querySelector('#full-record').open,identity:sub.getBoundingClientRect().toJSON(),
      identityText:sub.textContent,menu:menu.getBoundingClientRect().toJSON(),
      overflowingText,contrastFailures,targetFailures,lowestContrast:Number.isFinite(lowestContrast)?lowestContrast:null,textNodes};
  },{contrast,targets});
}
function recordLayout(label, layout, candidateOnly=true) {
  observations.push({label,...layout});
  if(!candidateOnly)return;
  check(`${label}: content reflows`, layout.scrollWidth<=layout.viewport+2 && !layout.overflowingText.length, layout.overflowingText);
  check(`${label}: text contrast`, !layout.contrastFailures.length, {minimum:layout.lowestContrast,failures:layout.contrastFailures});
  check(`${label}: targets at least44px`, !layout.targetFailures.length, layout.targetFailures);
}

async function main() {
  mkdirSync(output,{recursive:true});let current=candidate, fixtures={};const requests=[];
  const server=createServer((req,res)=>{
    const path=new URL(req.url,'http://127.0.0.1').pathname;requests.push({method:req.method,path});
    if(req.method!=='GET'){res.writeHead(405);res.end();return;}
    if(Object.hasOwn(fixtures,path)){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(fixtures[path]));return;}
    const file=path==='/'?current.html:current.files.get(path);
    if(file) {
      const type=path==='/'?'text/html; charset=utf-8':path.endsWith('.css')?'text/css':path.endsWith('.svg')?'image/svg+xml':'text/javascript';
      res.writeHead(200,{'Content-Type':type});res.end(file);
    } else {res.writeHead(503,{'Content-Type':'application/json'});res.end('{"state":"UNAVAILABLE","scope":"synthetic-browser-fixture"}');}
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin=`http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
    async function pageAt(options={}) {
      const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce',...options});
      const errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.fulfill({status:503,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:'{"state":"UNAVAILABLE","scope":"synthetic-browser-fixture"}'}));
      await page.goto(origin);
      if(options.javaScriptEnabled!==false)await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      return {page,errors};
    }
    for(const variant of baseline?.html?['baseline','candidate']:['candidate']) {
      current=variant==='baseline'?baseline:candidate;
      for(const width of [320,375,768,1440]) {
        const {page,errors}=await pageAt({viewport:{width,height:1000}});
        const closed=await inspect(page);recordLayout(`${variant}-${width}-closed`,closed,variant==='candidate');
        if(variant==='candidate') {
          check(`${width}: full identity preserved`,closed.identityText==='SZL Holdings / software & research');
          check(`${width}: navigation does not obscure identity`,!closed.menu.width || (closed.identity.right<=closed.menu.left-4 && closed.menu.width>=48 && closed.menu.height>=48));
          if(width===320||width===1440)await page.screenshot({path:resolve(output,`${variant}-${width}.png`)});
          if(width===320) {
            await page.locator('#menu-toggle').click();check('mobile menu opens',await page.locator('#menu-toggle').getAttribute('aria-expanded')==='true');
            await page.keyboard.press('Escape');check('Escape closes and returns focus',await page.locator('#menu-toggle').getAttribute('aria-expanded')==='false' && await page.locator('#menu-toggle').evaluate(el=>el===document.activeElement));
            await page.locator('#menu-toggle').click();await page.locator('#site-nav a[href="#platform"]').click();check('navigation follows its anchor and closes',await page.locator('#menu-toggle').getAttribute('aria-expanded')==='false');
          }
        }
        await page.locator('#full-record > summary').click();
        const opened=await inspect(page);recordLayout(`${variant}-${width}-open`,opened,variant==='candidate');
        if(variant==='candidate') {
          check(`${width}: source archive is native and opens`,opened.archiveOpen);
          if(width===1440)for(const selector of ['#nv-panel','#body-terra','footer'])if(await page.locator(selector).count())await page.locator(selector).screenshot({path:resolve(output,`${selector.replace(/[^a-z0-9]/gi,'')}-1440.png`)});
          check(`${width}: no page JavaScript errors`,!errors.length,errors);
        }
        await page.close();
      }
    }
    current=candidate;
    for(const scale of [2,4]) {
      const {page}=await pageAt({viewport:{width:1280,height:1000}});
      await page.evaluate(scale=>{document.documentElement.style.fontSize=`${16*scale}px`;document.querySelector('#full-record').open=true;},scale);
      recordLayout(`text-${scale*100}pct`,await inspect(page));
      await page.screenshot({path:resolve(output,`text-${scale*100}pct.png`)});await page.close();
    }
    {
      const {page}=await pageAt({viewport:{width:375,height:900},javaScriptEnabled:false});
      check('no JavaScript: navigation remains usable',await page.locator('#site-nav a[href="#platform"]').isVisible() && !await page.locator('#menu-toggle').isVisible());
      for(const id of ['nv-service','nv-doctrine','nv-kernel','nv-surfaces','nv-policy','nv-signer','nv-digest','nv-verdict'])check(`no JavaScript: ${id} stays unavailable`,await page.locator(`#${id}`).textContent()==='UNAVAILABLE');
      await page.locator('#full-record > summary').click();recordLayout('no-JavaScript-open',await inspect(page));await page.close();
    }
    {
      const {page}=await pageAt();
      await page.goto(`${origin}/#proof`);await page.waitForFunction(()=>document.querySelector('#full-record').open);
      check('deep link reveals preserved archive target',await page.locator('#proof').isVisible());
      await page.locator('#fw-hash-btn').focus();const focus=await page.locator('#fw-hash-btn').evaluate(el=>({active:document.activeElement===el,style:getComputedStyle(el).outlineStyle,width:getComputedStyle(el).outlineWidth}));
      check('byte-hash action has visible keyboard focus',focus.active&&focus.style!=='none'&&parseFloat(focus.width)>=2,focus);
      await page.keyboard.press('Enter');await page.waitForFunction(()=>document.querySelector('#fw-hash-out').textContent.includes('sha256:'));
      check('byte-hash output matches fetched page bytes',(await page.locator('#fw-hash-out').textContent()).trim()===`sha256:${sha(candidate.html)}`);
      await page.route(`${origin}/`,route=>route.fulfill({status:503,body:'unavailable'}));await page.locator('#fw-hash-btn').click();await page.waitForFunction(()=>document.querySelector('#fw-hash-out').textContent.includes('hash failed'));
      check('byte-hash HTTP failure remains explicit',(await page.locator('#fw-hash-out').textContent()).includes('hash failed'));
      check('shared enhancers leave one navigation owner',await page.locator('header.nav').count()===1 && await page.locator('.szl-flow-rail,.szl-holo-rail').count()===0);
      check('approved native marks loaded',await page.locator('img.brand-mark').evaluateAll(els=>els.length===2&&els.every(el=>el.complete&&el.naturalWidth>0)));
      check('whole-page clipping cannot conceal overflow',!['hidden','clip'].includes(await page.locator('body').evaluate(el=>getComputedStyle(el).overflowX)));
      await page.close();
    }
    {
      const {page}=await pageAt({forcedColors:'active',viewport:{width:375,height:900}});await page.locator('#full-record > summary').click();
      check('forced colors retains explicit specimen boundary',await page.locator('.specimen-card').evaluate(el=>getComputedStyle(el).borderTopStyle!=='none'&&parseFloat(getComputedStyle(el).borderTopWidth)>=1));
      check('forced colors removes decorative atmosphere',!await page.locator('.holo-field').isVisible());
      recordLayout('forced-colors-open',await inspect(page,{contrast:false}));await page.screenshot({path:resolve(output,'forced-colors.png')});await page.close();
    }
    for(const [signed,verified,expected] of [[false,false,'HASH-LINKED'],[true,false,'HASH-LINKED'],[true,true,'SIGNED']]) {
      const label='<img src=x onerror="window.untrustedLabelExecuted=true">';
      fixtures={
        '/api/a11oy/healthz':{service:'LOCAL_BROWSER_FIXTURE',rollup:{signer:{status:'SOURCE_REPORTED_FIXTURE'}}},
        '/api/a11oy/v1/honest':{service:'LOCAL_BROWSER_FIXTURE',doctrine:'v11',doctrine_lock:{doctrine:'v11'},locked_formula_count:8},
        '/api/a11oy/v1/frontier/surfaces':{count:3,summary:{present:1,unavailable:2,label_counts:{ROADMAP:1,UNAVAILABLE:1,[label]:1}}},
        '/api/a11oy/v1/attest/manifest':{verdict:'BLOCKED',label:'SAMPLE',statement_digest_sha256:'a'.repeat(64),verification:{signature:{signed,verified}}},
      };
      const {page,errors}=await pageAt({viewport:{width:375,height:1000}});
      await page.waitForFunction(expected=>document.querySelector('#nv-verdict').textContent===expected,expected);
      const state=await page.locator('#nv-panel').evaluate(el=>({kernel:el.querySelector('#nv-kernel').textContent,state:el.querySelector('#nv-state').textContent,live:el.classList.contains('is-live'),policy:el.querySelector('#nv-policy').textContent}));
      check(`signature flags ${signed}/${verified}: exact verdict`,await page.locator('#nv-verdict').textContent()===expected);
      check(`signature flags ${signed}/${verified}: metadata is not readiness`,state.kernel==='8 locked · reported'&&state.state==='metadata observed · not readiness'&&!state.live&&state.policy==='BLOCKED · SAMPLE',state);
      check(`signature flags ${signed}/${verified}: provider label stays literal`,(await page.locator('#nv-legend').textContent()).includes(label)&&await page.locator('#nv-legend img').count()===0&&!await page.evaluate(()=>Boolean(window.untrustedLabelExecuted)));
      recordLayout(`populated-${signed}-${verified}`,await inspect(page));
      check(`signature flags ${signed}/${verified}: no JavaScript errors`,!errors.length,errors);
      await page.close();
    }
    fixtures={};
    {
      const {page}=await pageAt({viewport:{width:360,height:800}});
      const actions=await page.locator('.hero .cta-row a').evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return {width:r.width,height:r.height,bottom:r.bottom};}));
      check('short phone: full hero action targets fit first fold',actions.length===2&&actions.every(r=>r.width>=44&&r.height>=52&&r.bottom<=800),actions);
      for(const state of ['hover','pressed']){
        await page.locator('.hero-artifact').hover();if(state==='pressed')await page.mouse.down();
        const layout=await inspect(page);
        check(`primary action ${state}: text contrast`,!layout.contrastFailures.length,layout.contrastFailures);
        if(state==='pressed')await page.mouse.up();
      }
      await page.close();
    }
    check('read-only page made no write requests',requests.every(r=>r.method==='GET'),requests.filter(r=>r.method!=='GET'));
    check('candidate stylesheet is bound and available',candidate.files.get('/assets/a11oy-homepage.css')?.length>0&&candidate.html.includes('id="szl-homepage-shell"'));
  } finally {
    if(browser)await browser.close();await new Promise(r=>server.close(r));
    const assets=Object.fromEntries([...candidate.files].filter(([,bytes])=>bytes).map(([url,bytes])=>[url,sha(bytes)]));
    writeFileSync(resolve(output,'landing-reflow-results.json'),JSON.stringify({observed_at:new Date().toISOString(),scope:'LOCAL_SOURCE_BROWSER_CONTROLLED_PROVIDER_FIXTURES',source_html_sha256:sha(candidate.html),assets,base_sha:base||null,baseline_state:baseline?.html?'OBSERVED':base?'UNAVAILABLE':'NOT_REQUESTED',baseline_assets_pinned_to_base:true,limits:['Chromium only','Synthetic unavailable responses and explicit signed/verified state fixtures; no live-provider verdict','Computed text contrast excludes decorative SVGs; no overall WCAG or field performance verdict'],results,observations},null,2)+'\n');
  }
  const failed=results.filter(r=>!r.ok);console.log(JSON.stringify({checks:results.length,passed:results.length-failed.length,failed},null,2));
  assert.equal(failed.length,0,'candidate must preserve content, identity, controls and honest states');
}
main().catch(error=>{console.error(error);process.exitCode=1});
