// Real model registry — distilled from puriq/llms/A11OY_CODE_ROUTER_SPEC.md and OPEN_LLM_LANDSCAPE_2026.md.
// license: GREEN (Apache/MIT), AMBER (community/Llama/TII), RED (research-only).
// tier: T0..T6. ctx in tokens. mmlu/bench = routing-relevant score. hf = repo id where known.
export const TIERS = [
  ['T0','Trivial / cached','<50ms'],
  ['T1','Small fast','<400ms'],
  ['T2','Standard','<2s'],
  ['T3','Code-specialized','<3s'],
  ['T4','Reasoning-heavy','<15s'],
  ['T5','Long-context','<10s'],
  ['T6','Multimodal','<5s'],
];

// Organ ids are Quechua codenames (doctrine v11). Banned codenames amaru/sentra
// are retired -> YACHAY (governance/receipts) / CHAPAQ (security gates).
export const ORGANS = [
  ['a11oy','coding brain','T3'],
  ['yachay','governance / receipts','T2'],
  ['chapaq','security gates','T1'],
  ['rosie','orchestration','T2'],
  ['vessels','maritime intel','T6'],
  ['killinchu','maritime intel','T2'],
];

export const MODELS = [
  // T0
  {name:'Arctic-embed-L',tier:'T0',license:'GREEN',ctx:'n/a',bench:'MTEB >55.9',prov:'embed',hf:'Snowflake/snowflake-arctic-embed-l',role:'text→vector + cache'},
  // T1
  {name:'Mistral Small 3 24B',tier:'T1',license:'GREEN',ctx:'32K',bench:'MMLU ~81',prov:'DeepInfra',hf:'mistralai/Mistral-Small-24B-Instruct-2501'},
  {name:'Phi-4 14B',tier:'T1',license:'GREEN',ctx:'16K',bench:'GPQA 56.1',prov:'low',hf:'microsoft/phi-4'},
  {name:'Qwen3-8B',tier:'T1',license:'GREEN',ctx:'128K',bench:'fast triage',prov:'DeepInfra',hf:'Qwen/Qwen3-8B'},
  {name:'Granite 3.3 8B',tier:'T1',license:'GREEN',ctx:'128K',bench:'RAG LoRA',prov:'low',hf:'ibm-granite/granite-3.3-8b-instruct'},
  // T2
  {name:'Llama 3.3 70B',tier:'T2',license:'AMBER',ctx:'128K',bench:'IFEval 92.1 / HumanEval 88.4',prov:'Groq',hf:'meta-llama/Llama-3.3-70B-Instruct'},
  {name:'DeepSeek V3',tier:'T2',license:'GREEN',ctx:'164K',bench:'MMLU 88.5',prov:'DeepInfra',hf:'deepseek-ai/DeepSeek-V3'},
  {name:'OLMo 2 32B',tier:'T2',license:'GREEN',ctx:'4K',bench:'clean lineage',prov:'self-host',hf:'allenai/OLMo-2-0325-32B-Instruct'},
  {name:'Hermes 4 70B',tier:'T2',license:'AMBER',ctx:'128K',bench:'schema-bound',prov:'Together',hf:'NousResearch/Hermes-4-70B'},
  {name:'Yi 1.5 34B',tier:'T2',license:'GREEN',ctx:'32K',bench:'MMLU 77',prov:'self-host',hf:'01-ai/Yi-1.5-34B-Chat'},
  {name:'InternLM 2.5 20B',tier:'T2',license:'GREEN',ctx:'256K',bench:'long-ctx',prov:'self-host',hf:'internlm/internlm2_5-20b-chat'},
  {name:'DBRX Instruct',tier:'T2',license:'AMBER',ctx:'32K',bench:'MoE 132B',prov:'DeepInfra',hf:'databricks/dbrx-instruct'},
  // T3
  {name:'Codestral 25.01',tier:'T3',license:'AMBER',ctx:'256K',bench:'HumanEval 86.6 / FIM SOTA',prov:'Mistral',hf:'mistralai/Codestral-2501'},
  {name:'Qwen2.5-72B',tier:'T3',license:'AMBER',ctx:'131K',bench:'HumanEval 86.6',prov:'Together',hf:'Qwen/Qwen2.5-72B-Instruct'},
  {name:'Qwen2.5-Coder 32B',tier:'T3',license:'GREEN',ctx:'131K',bench:'code SOTA OSS',prov:'DeepInfra',hf:'Qwen/Qwen2.5-Coder-32B-Instruct'},
  {name:'DeepSeek Coder V2',tier:'T3',license:'GREEN',ctx:'128K',bench:'HumanEval 90+',prov:'DeepInfra',hf:'deepseek-ai/DeepSeek-Coder-V2-Instruct'},
  // T4
  {name:'DeepSeek R1',tier:'T4',license:'GREEN',ctx:'131K',bench:'MATH-500 frontier (long-CoT)',prov:'Together',hf:'deepseek-ai/DeepSeek-R1'},
  {name:'Qwen3-235B-A22B',tier:'T4',license:'GREEN',ctx:'128K',bench:"AIME'24 85.7 / LCB 70.7",prov:'Together',hf:'Qwen/Qwen3-235B-A22B'},
  {name:'QwQ 32B',tier:'T4',license:'GREEN',ctx:'131K',bench:'reasoning',prov:'DeepInfra',hf:'Qwen/QwQ-32B'},
  {name:'Mistral Large 3',tier:'T4',license:'GREEN',ctx:'128K',bench:'reasoning',prov:'Mistral',hf:'mistralai/Mistral-Large-Instruct-2411'},
  // T5
  {name:'Llama 4 Scout',tier:'T5',license:'AMBER',ctx:'10M',bench:'MMLU 79.6',prov:'DeepInfra/Groq',hf:'meta-llama/Llama-4-Scout-17B-16E-Instruct'},
  {name:'Falcon-H1 34B',tier:'T5',license:'AMBER',ctx:'262K',bench:'hybrid SSM long-ctx',prov:'self-host',hf:'tiiuae/Falcon-H1-34B-Instruct'},
  {name:'Jamba 1.5 Large',tier:'T5',license:'AMBER',ctx:'256K',bench:'SSM-hybrid',prov:'self-host',hf:'ai21labs/AI21-Jamba-1.5-Large'},
  // T6
  {name:'Llama 4 Maverick',tier:'T6',license:'AMBER',ctx:'1M',bench:'MMLU 85.5 / image grounding',prov:'DeepInfra',hf:'meta-llama/Llama-4-Maverick-17B-128E-Instruct'},
  {name:'Gemma 3 27B',tier:'T6',license:'AMBER',ctx:'128K',bench:'DocVQA 85.6 / MMMU 64.9',prov:'low',hf:'google/gemma-3-27b-it'},
  {name:'Phi-4-multimodal',tier:'T6',license:'GREEN',ctx:'128K',bench:'MMMU 55.1 (+audio)',prov:'low',hf:'microsoft/Phi-4-multimodal-instruct'},
  {name:'Qwen2.5-VL 72B',tier:'T6',license:'AMBER',ctx:'128K',bench:'vision strong',prov:'DeepInfra',hf:'Qwen/Qwen2.5-VL-72B-Instruct'},
  {name:'InternVL 2.5 38B',tier:'T6',license:'GREEN',ctx:'32K',bench:'MMMU 63',prov:'self-host',hf:'OpenGVLab/InternVL2_5-38B'},
  // RED (research-only) — API-only
  {name:'Cohere Command A',tier:'T2',license:'RED',ctx:'256K',bench:'RAG strong',prov:'cohere',hf:'CohereForAI/c4ai-command-a-03-2025'},
  {name:'Cohere Command R+',tier:'T2',license:'RED',ctx:'128K',bench:'RAG/tool',prov:'cohere',hf:'CohereForAI/c4ai-command-r-plus-08-2024'},
  // extra GREEN reasoning/general to exceed 30
  {name:'OLMo 2 13B',tier:'T1',license:'GREEN',ctx:'4K',bench:'open data',prov:'self-host',hf:'allenai/OLMo-2-1124-13B-Instruct'},
  {name:'Gemma 3 12B',tier:'T2',license:'AMBER',ctx:'128K',bench:'MMLU 74',prov:'low',hf:'google/gemma-3-12b-it'},
];

// ---------------------------------------------------------------------------
// GRAPH ROUTER LAYER (clean-room). The classic deterministic tier picker is
// replaced by a learned bipartite query<->model affinity graph in the spirit of
// the published open routers below (attributed in THIRD_PARTY_NOTICES; NO code
// copied — only the concept of edge-weighted query/model graphs):
//   - GraphRouter (MIT)   — graph-based inductive LLM routing over query/task/model nodes
//   - Router-R1 (Apache-2.0) — RL multi-round router as a reasoning graph
//   - LLMRouter (MIT)     — cost/quality edge weighting across a model pool
// Each TASK is a query-side node; each MODEL is a model-side node; an EDGE carries
// a transparent affinity weight = quality_fit x ctx_fit x license_pref / cost_proxy.
// Weights are computed locally from declared bench/ctx/license features (honest:
// these are heuristic affinities derived from the public model card numbers above,
// NOT measured online benchmarks — labelled as such in the UI).
export const TASKS = [
  {id:'code',         label:'Code synthesis / repair', tier:'T3', weights:{quality:0.45,ctx:0.20,cost:0.20,green:0.15}},
  {id:'reasoning',    label:'Multi-step reasoning',    tier:'T4', weights:{quality:0.55,ctx:0.15,cost:0.10,green:0.20}},
  {id:'long_context', label:'Long-context / RAG',      tier:'T5', weights:{quality:0.30,ctx:0.45,cost:0.10,green:0.15}},
  {id:'document_vision',label:'Document / vision',     tier:'T6', weights:{quality:0.40,ctx:0.20,cost:0.10,green:0.30}},
  {id:'classify',     label:'Classify / triage',       tier:'T1', weights:{quality:0.25,ctx:0.10,cost:0.50,green:0.15}},
  {id:'general',      label:'General assistant',       tier:'T2', weights:{quality:0.40,ctx:0.20,cost:0.20,green:0.20}},
  {id:'embed',        label:'Embed / cache',           tier:'T0', weights:{quality:0.30,ctx:0.05,cost:0.55,green:0.10}},
];

// Each organ emits a task mix (sums ~1.0) — the router fans these across models.
export const ORGAN_TASKMIX = {
  a11oy:    {code:0.6, reasoning:0.2, general:0.2},
  yachay:   {general:0.5, reasoning:0.3, classify:0.2},
  chapaq:   {classify:0.6, reasoning:0.2, general:0.2},
  rosie:    {general:0.5, long_context:0.3, reasoning:0.2},
  vessels:  {document_vision:0.6, long_context:0.2, general:0.2},
  killinchu:{general:0.5, classify:0.3, long_context:0.2},
};

// --- transparent feature extractors from the public model-card strings ---
function _ctxTokens(c){
  if(!c) return 0; const s=String(c).toUpperCase();
  const m=s.match(/([\d.]+)\s*([KM]?)/); if(!m) return 0;
  let n=parseFloat(m[1])||0; if(m[2]==='K')n*=1e3; else if(m[2]==='M')n*=1e6; return n;
}
function _qualityProxy(m){
  // pull the largest numeric benchmark score from the bench string (0..100),
  // fall back to a tier prior when no number is present (honest heuristic).
  const nums=(String(m.bench).match(/\d+(?:\.\d+)?/g)||[]).map(Number).filter(n=>n<=100);
  const benchMax=nums.length?Math.max(...nums):0;
  const tierPrior={T0:55,T1:70,T2:80,T3:84,T4:88,T5:78,T6:80}[m.tier]||70;
  return Math.max(benchMax, tierPrior)/100;            // 0..1
}
function _costProxy(m){
  // cheaper (lower) is better; rough proxy by tier latency band + provider.
  const band={T0:0.1,T1:0.2,T2:0.4,T3:0.5,T4:0.9,T5:0.7,T6:0.6}[m.tier]||0.5;
  const hosted=/self-host|low/i.test(m.prov||'')?0.85:1.0;  // self-host = cheaper
  return Math.max(0.08, band*hosted);                  // 0..1, lower=cheaper
}

// EDGE WEIGHT: affinity(task, model) in [0,1]. Transparent, deterministic.
export function edgeAffinity(task, m){
  const w=task.weights;
  const q=_qualityProxy(m);
  const ctxTok=_ctxTokens(m.ctx);
  // ctx fit: saturating — long-context tasks reward big windows, others cap fast.
  const ctxNeed = task.id==='long_context' ? 1e6 : task.id==='document_vision' ? 2e5 : 6e4;
  const ctxFit=Math.min(1, ctxTok/ctxNeed);
  const cost=1-_costProxy(m);                          // higher=cheaper=better
  const green=m.license==='GREEN'?1: m.license==='AMBER'?0.55:0.2;
  const score=w.quality*q + w.ctx*ctxFit + w.cost*cost + w.green*green;
  return {score:Math.max(0,Math.min(1,score)), q, ctxFit, cost, green};
}

// Rank models for a task; returns sorted [{m, aff}] best-first.
export function rankForTask(task, models, sovereign){
  const pool = sovereign ? models.filter(m=>m.license==='GREEN') : models;
  return pool.map(m=>({m, aff:edgeAffinity(task, m)}))
             .sort((a,b)=>b.aff.score-a.aff.score);
}
