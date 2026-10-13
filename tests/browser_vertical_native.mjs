// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import {readFile,writeFile,mkdtemp,lstat} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const args=Object.fromEntries(process.argv.slice(2).reduce((a,v,i,all)=>i%2?a:[...a,[v,all[i+1]]],[]));
const parent=path.resolve(args['--out']);
if(!(await lstat(parent)).isDirectory())throw Error('output parent must be a regular directory');
const out=await mkdtemp(path.join(parent,'vertical-native-'));
const fixture=path.join(out,'fixtures');
const child=spawnSync('python',['tests/materialize_vertical_native.py',fixture],{encoding:'utf8',env:{PATH:process.env.PATH,HOME:out,PYTHONDONTWRITEBYTECODE:'1',LANG:'C.UTF-8'}});
if(child.status!==0)throw Error(child.stderr||'fixture materialization failed');
const source=JSON.parse(await readFile(path.join(fixture,'source.json'),'utf8'));
const names=['counsel','finance','sentra','terra','terra-landing'];
const pages={};
for(const name of names){const raw=await readFile(path.join(fixture,name+'.html'));if(createHash('sha256').update(raw).digest('hex')!==source.files[name+'.html'])throw Error('fixture byte mismatch');pages[name]=raw;}
const {chromium}=await import(pathToFileURL(path.resolve(args['--module'])).href);
const report={schema:'szl.vertical-native-browser/v1',source,scope:'unsigned browser-context observations over actual generated HTML; all API responses are explicit unavailable fixtures; no provider or publisher',checks:[],failures:[],cases:[],denied:[]};
const check=(name,ok,detail=null)=>{const row={name,passed:!!ok,detail};report.checks.push(row);if(!ok)report.failures.push(row);};
const browser=await chromium.launch({headless:true});
try{
for(const name of names){
 for(const variant of [{name:'wide',width:1440},{name:'tablet',width:768},{name:'phone',width:375},{name:'narrow',width:320},{name:'motion',width:375,reducedMotion:'reduce'},{name:'contrast',width:375,forcedColors:'active'}]){
  const label=name+'/'+variant.name;
  const context=await browser.newContext({viewport:{width:variant.width,height:960},reducedMotion:variant.reducedMotion||'no-preference',forcedColors:variant.forcedColors||'none',serviceWorkers:'block'});
  await context.route('**/*',async route=>{const r=route.request(),u=new URL(r.url());
   if(u.origin!=='https://native.invalid'||r.method()!=='GET'){report.denied.push({url:r.url(),method:r.method()});await route.abort();return;}
   if(u.pathname==='/'+name){await route.fulfill({status:200,contentType:'text/html',body:pages[name]});return;}
   if(u.pathname.startsWith('/api/')){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({status:'UNAVAILABLE',error:'BROWSER_FIXTURE_UNAVAILABLE',ok:false,receipt_verified:false})});return;}
   report.denied.push({url:r.url(),method:r.method()});await route.abort();
  });
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('https://native.invalid/'+name,{waitUntil:'networkidle'});
  const metric=await page.evaluate(()=>{
   const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
   const overflow=[...document.querySelectorAll('main *')].filter(visible).filter(e=>{const r=e.getBoundingClientRect();if(e.closest('.fin-scroll')||e.tagName==='svg'||e.closest('svg'))return false;return r.left < -1||r.right>innerWidth+1;}).map(e=>({tag:e.tagName,id:e.id,class:e.className,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}));
   const targets=[...document.querySelectorAll('main a,button,summary,input,select,textarea')].filter(visible).map(e=>({text:e.textContent.trim().slice(0,50),id:e.id,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}));
   const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
   const rgba=s=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=s;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data];};
   const lum=c=>c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,b,i)=>a+b*[.2126,.7152,.0722][i],0);
   const contrasts=[];
   for(const e of document.querySelectorAll('main p,main h1,main h2,main h3,main a,main label,main button,main summary,main pre,main span,main b,main .cite,main .mono')){
    if(!visible(e)||![...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))continue;
    const s=getComputedStyle(e);let p=e,bg;
    while(p){const c=rgba(getComputedStyle(p).backgroundColor);if(c[3]===255){bg=c;break;}p=p.parentElement;}
    if(!bg){contrasts.push({text:e.textContent.slice(0,55),unsupported:true});continue;}
    const f=lum(rgba(s.color)),b=lum(bg),ratio=(Math.max(f,b)+.05)/(Math.min(f,b)+.05);
    const large=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&Number(s.fontWeight)>=700);
    contrasts.push({text:e.textContent.slice(0,55),id:e.id,ratio,minimum:large?3:4.5});
   }
   const status=document.querySelector('#st,#livepill');
   return{width:innerWidth,scroll:document.documentElement.scrollWidth,overflow,targets,contrasts,polarity:document.documentElement.dataset.surface,statusRole:status?.getAttribute('role'),statusText:status?.textContent,iris:document.documentElement.dataset.iris,images:[...document.querySelectorAll('.native-identity img')].map(e=>({loaded:e.complete&&e.naturalWidth>0,width:e.getBoundingClientRect().width})),motion:[...document.querySelectorAll('main *')].filter(visible).filter(e=>getComputedStyle(e).animationName!=='none').length};
  });
  check(label+' reflow',metric.scroll<=variant.width+1&&metric.overflow.length===0,metric.overflow);
  check(label+' native icon bytes render at40',metric.images.length===1&&metric.images[0].loaded&&metric.images[0].width===40);
  check(label+' touch controls',metric.targets.every(t=>t.height>=44&&t.width>=24),metric.targets.filter(t=>t.height<44||t.width<24));
  check(label+' status is announced unavailable',metric.statusRole==='status'&&metric.statusText.includes('UNAVAILABLE'),metric.statusText);
  if(variant.forcedColors!=='active')check(label+' opaque-ground text contrast',metric.contrasts.every(c=>!c.unsupported&&c.ratio>=c.minimum),metric.contrasts.filter(c=>c.unsupported||c.ratio<c.minimum));
  if(name==='sentra')check(label+' iris remains closed',metric.iris==='closed');
  if(variant.reducedMotion==='reduce')check(label+' reduced motion',metric.motion===0);
  await page.keyboard.press('Tab');check(label+' skip first',await page.locator('.native-skip').evaluate(e=>e===document.activeElement&&e.getBoundingClientRect().top>=0));
  await page.keyboard.press('Enter');check(label+' skip focuses main',await page.locator('main').evaluate(e=>e===document.activeElement));
  for(const link of await page.locator('.native-nav a[href^="#"]').all()){
   await link.focus();await page.keyboard.press('Enter');const dest=await link.getAttribute('href');check(label+' navigation '+dest,new URL(page.url()).hash===dest&&await page.locator(dest).count()===1);
  }
  check(label+' no page errors',errors.length===0,errors);
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,name+'-'+variant.name+'.png'),fullPage:true});
  report.cases.push({name,variant,metric,errors});await context.close();
 }
 const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:375,height:960}});
 await context.route('**/*',r=>r.fulfill({status:200,contentType:'text/html',body:pages[name]}));
 const page=await context.newPage();await page.goto('https://native.invalid/'+name);check(name+' no JavaScript explanation',await page.locator('.native-noscript').isVisible());await context.close();
}
check('no remote or write browser attempts',report.denied.length===0,report.denied);
}catch(e){check('suite completed',false,String(e.stack||e));}
finally{await browser.close();report.passed=report.checks.filter(c=>c.passed).length;report.total=report.checks.length;await writeFile(path.join(out,'results.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});}
console.log(JSON.stringify({out,passed:report.passed,total:report.total,failures:report.failures}));if(report.failures.length)process.exitCode=1;
