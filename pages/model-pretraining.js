/* Presentation of the existing public snapshot. No model execution or training. */
const ENDPOINT = '/api/a11oy/v1/models/pretraining';
const CATEGORIES = ['ADAPTER_HINT','CHECKPOINT_HINT','GGUF_HINT','CLASSICAL_MODEL_HINT',
  'KERNEL_OR_SOFTWARE_HINT','RECIPE_OR_PLACEHOLDER_HINT','UNCLASSIFIED'];
const label = (value) => value.replace(/_HINT$/, '').replaceAll('_',' ').toLowerCase();
const requireValue = (ok) => { if (!ok) throw new Error('Inventory response does not satisfy the read-only contract.'); };
export function validate(value) {
  requireValue(value?.schema === 'szl.model-pretraining-view/v1' && value.available === true
    && value.state === 'PRETRAINING_REVIEW_NOT_ALIGNMENT' && value.trainingAllowed === false
    && value.sourceAlignmentVerified === false && value.wholeOrganizationInventoryVerified === false
    && value.inventoryScope?.visibility === 'public-only' && value.inventoryScope.authenticated === false
    && value.inventoryScope.privateAssetsIncluded === false);
  requireValue(value.authority && ['training','inference','publication','promotion','deletion','toolExecution']
    .every(key => value.authority[key] === false) && Object.keys(value.authority).length === 6);
  requireValue(Array.isArray(value.models) && value.models.length <= 2000
    && Number.isInteger(value.returned) && value.returned === value.models.length
    && Number.isInteger(value.sourcePointersDeclared) && value.sourcePointersDeclared >= 0
    && value.sourcePointersDeclared <= value.models.length
    && /^[a-f0-9]{64}$/.test(value.manifestSha256)
    && typeof value.observedAt === 'string' && /(?:Z|[+-]\d\d:\d\d)$/.test(value.observedAt)
    && Number.isFinite(Date.parse(value.observedAt))
    && ['CLOCK_SKEW','STALE_SNAPSHOT','SNAPSHOT_NOT_LIVE'].includes(value.snapshotFreshness)
    && Array.isArray(value.bounds) && value.bounds.length <= 20
    && value.bounds.every(bound => typeof bound === 'string' && bound.length <= 2048));
  const seen = new Set(); let linked = 0;
  const counts = {};
  for (const row of value.models) {
    requireValue(/^SZLHOLDINGS\/[A-Za-z0-9][A-Za-z0-9._-]{0,159}$/.test(row.id)
      && !row.id.includes('..') && !seen.has(row.id) && /^[a-f0-9]{40}$/.test(row.hubRevision)
      && CATEGORIES.includes(row.categoryHint) && row.categoryIsVerified === false
      && ['DECLARED_POINTER_ONLY','AMBIGUOUS','NOT_RESOLVED_BY_THIS_CATALOG'].includes(row.sourceState)
      && row.hubRevisionState === 'RECORDED_SNAPSHOT_NOT_LIVE'
      && typeof row.nextAction === 'string' && row.nextAction.length <= 1024
      && (typeof row.gated === 'boolean' || ['auto','manual'].includes(row.gated))
      && typeof row.disabled === 'boolean'
      && ['weightsVerified','sourceBytesVerified','evaluationVerified','publicationVerified','runtimeVerified','trainingAllowed']
        .every(key => row[key] === false));
    seen.add(row.id); counts[row.categoryHint] = (counts[row.categoryHint] || 0) + 1;
    if (row.sourceState === 'DECLARED_POINTER_ONLY') { requireValue(safeSource(row.sourceUrl)); linked++; }
  }
  requireValue(linked === value.sourcePointersDeclared && value.categoryCounts &&
    Object.keys(value.categoryCounts).length === Object.keys(counts).length &&
    Object.entries(counts).every(([key,count]) => value.categoryCounts[key] === count));
  return value;
}
export function safeSource(value) {
  if (typeof value !== 'string' || value.length > 1024 || /[\x00-\x20\x7f]/.test(value)) return null;
  try { const url = new URL(value); return url.protocol === 'https:' && url.host === 'github.com'
    && !url.username && !url.password && !url.search && !url.hash
    && /^\/szl-holdings\/[A-Za-z0-9._-]+(?:\/[A-Za-z0-9._-]+)*$/.test(url.pathname)
    && !value.includes('%') && !value.split('/').some(part => part === '.' || part === '..') && !value.includes('\\') ? url.href : null;
  } catch { return null; }
}
export function filterRows(rows, query, category) {
  const q = query.trim().toLowerCase();
  return rows.filter(row => (category === 'ALL' || row.categoryHint === category)
    && `${row.id} ${row.categoryHint}`.toLowerCase().includes(q));
}
function boot() {
  const $ = id => document.getElementById(id);
  if (!$('models')) return;
  let state = null, generation = 0, active = null;
  function text(tag, value, className) { const element = document.createElement(tag); element.textContent = value;
    if (className) element.className = className; return element; }
  function link(title, href) { const a = text('a',title); a.href = href; a.rel = 'noreferrer noopener'; return a; }
  function clear() {
    state = null; $('models').replaceChildren(); $('total').textContent = '—'; $('sources').textContent = '—';
    $('shown').textContent = ''; $('observed').textContent = 'Unavailable'; $('manifest-hash').textContent = 'Unavailable';
    $('product-source').textContent = 'Unavailable'; $('bounds').replaceChildren();
    $('search').disabled = true; $('category').disabled = true;
  }
  function render() {
    if (!state) return;
    const rows = filterRows(state.models,$('search').value,$('category').value);
    $('models').replaceChildren(); $('shown').textContent = `${rows.length} of ${state.returned} recorded entries shown. Categories are metadata hints, not qualifications.`;
    for (const row of rows) {
      const article = text('article','', 'card');
      article.append(text('span',label(row.categoryHint),'tag'),text('h2',row.id.split('/')[1]),text('p',row.nextAction));
      article.append(text('div', row.sourceState === 'DECLARED_POINTER_ONLY'
        ? 'Source pointer recorded · source bytes unverified' : 'Model source mapping unresolved in this catalog','record-state'));
      article.append(text('div','Weight, evaluation and runtime checks not verified here','record-state'));
      if (row.gated) article.append(text('p','Access-controlled artifact · use the owner-approved access path.'));
      if (row.disabled) article.append(text('p','Snapshot reports this repository disabled.'));
      const links = text('div','','links');
      links.append(link('Recorded Hub revision',`https://huggingface.co/${row.id}/tree/${row.hubRevision}`));
      const source = safeSource(row.sourceUrl); if (source) links.append(link('Declared code',source));
      article.append(links); $('models').append(article);
    }
  }
  async function boundedJson(response) {
    if (!response.body) throw new Error('No response body.');
    const reader = response.body.getReader(), chunks = []; let length = 0;
    try { while (true) { const {done,value} = await reader.read(); if (done) break;
      length += value.byteLength; if (length > 4000000) throw new Error('Inventory response exceeds its size limit.'); chunks.push(value);
    }} finally { await reader.cancel(); }
    const bytes = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk,offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  }
  async function load() {
    const ticket = ++generation; active?.abort(); active = new AbortController(); const own = active;
    clear(); $('reload').disabled = true; $('status').textContent = 'Reading the packaged inventory…';
    const timeout = setTimeout(()=>own.abort(),15000);
    try {
      const response = await fetch(ENDPOINT,{cache:'no-store',credentials:'omit',redirect:'error',signal:own.signal,
        headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error(`Inventory unavailable (HTTP ${response.status}). No missing inventory is treated as zero.`);
      const value = validate(await boundedJson(response)); if (ticket !== generation) return;
      state = value; $('total').textContent = String(value.returned); $('sources').textContent = String(value.sourcePointersDeclared);
      $('status').textContent = `${value.snapshotFreshness.replaceAll('_',' ')} · ${value.observedAt}. GitHub–Hub alignment is not certified. Training remains outside this interface.`;
      $('observed').textContent = value.observedAt; $('manifest-hash').textContent = value.manifestSha256;
      $('product-source').textContent = value.productSourceRevisionReported || 'Unavailable — no runtime source inferred';
      for (const bound of value.bounds || []) $('bounds').append(text('li',bound));
      const previous = $('category').value; $('category').replaceChildren();
      for (const name of ['ALL',...CATEGORIES]) {const option = text('option',name === 'ALL' ? 'All categories' : label(name)); option.value=name; $('category').append(option);}
      $('category').value = previous; $('search').disabled = false; $('category').disabled = false; render();
    } catch(error) { if(ticket !== generation) return; clear(); $('status').textContent = error.name === 'AbortError'
      ? 'Inventory request timed out. No stale success is shown.' : error.message;
    } finally {clearTimeout(timeout); if(ticket === generation) $('reload').disabled=false;}
  }
  $('search').addEventListener('input',render); $('category').addEventListener('change',render);
  $('reload').addEventListener('click',load); load();
}
if (typeof document !== 'undefined') boot();
