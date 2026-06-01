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

export const ORGANS = [
  ['a11oy','coding brain','T3'],
  ['amaru','governance / receipts','T2'],
  ['sentra','security gates','T1'],
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
