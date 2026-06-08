# Third-Party Notices — SZL Holdings Flagships
**Doctrine v11 LOCKED 749/14/163 | SLSA L1 honest | Generated: 2026-06-03**

This file contains notices for third-party libraries used by SZL Holdings flagships.

## Python Dependencies

### FastAPI
- **License:** MIT
- **Source:** https://github.com/tiangolo/fastapi
- **Usage:** API framework for all 5 flagships

### Gradio
- **License:** Apache-2.0
- **Source:** https://github.com/gradio-app/gradio
- **Usage:** UI framework for HuggingFace Spaces

### Uvicorn
- **License:** BSD-3-Clause
- **Source:** https://github.com/encode/uvicorn
- **Usage:** ASGI server

### httpx
- **License:** BSD-3-Clause
- **Source:** https://github.com/encode/httpx
- **Usage:** HTTP client for inter-flagship calls

### huggingface_hub
- **License:** Apache-2.0
- **Source:** https://github.com/huggingface/huggingface_hub
- **Usage:** HuggingFace API access

## Infrastructure Components

### UDS Core (Defense Unicorns)
- **License:** Apache-2.0
- **Source:** https://github.com/defenseunicorns/uds-core
- **Usage:** Kubernetes security baseline (UDS deployment)

### Zarf (Defense Unicorns)
- **License:** Apache-2.0  
- **Source:** https://github.com/zarf-dev/zarf
- **Usage:** Airgap packaging

### Pepr (Defense Unicorns)
- **License:** Apache-2.0
- **Source:** https://github.com/defenseunicorns/pepr
- **Usage:** Kubernetes admission webhook

## Mathematical Libraries

### Lean 4 (Lean FRO / Microsoft Research)
- **License:** Apache-2.0
- **Source:** https://github.com/leanprover/lean4
- **Usage:** Formal verification substrate (lutar-lean)

### Mathlib4
- **License:** Apache-2.0
- **Source:** https://github.com/leanprover-community/mathlib4
- **Usage:** Mathematical library for Lean 4

## Frontend Routing Visualization (clean-room — concept attribution)

The a11oy console `llm` tab (`console/static/viz/router/`) implements a
**graph-based LLM router** visualization. The implementation is **clean-room**:
no third-party source code is copied or bundled. The design follows the published
*concept* of edge-weighted query/task↔model routing graphs introduced by the
following open projects, attributed here in good faith:

### GraphRouter
- **License:** MIT
- **Source:** https://github.com/ulab-uiuc/GraphRouter
- **Usage (concept only):** graph-based, inductive LLM routing over query/task/model nodes — inspiration for the bipartite affinity-graph layout and edge weighting. No code copied.

### Router-R1
- **License:** Apache-2.0
- **Source:** https://github.com/ulab-uiuc/Router-R1
- **Usage (concept only):** treating routing as a multi-round reasoning graph — inspiration for the per-task fan-out / top-K edge selection. No code copied.

### LLMRouter
- **License:** MIT
- **Source:** https://github.com/lm-sys/RouteLLM
- **Usage (concept only):** cost/quality trade-off across a model pool — inspiration for the transparent quality×ctx×cost×license edge-affinity weight. No code copied.

All edge-affinity scores are heuristic, computed locally from public model-card
features (declared benchmark/context/license), and are labelled in-UI as
heuristic (not measured online benchmarks). No routing data is fabricated.

### three.js
- **License:** MIT
- **Source:** https://github.com/mrdoob/three.js
- **Usage:** 3D rendering for the routing-graph and other console viz pages (r171).

## Section 889 Declaration

SZL Holdings does NOT use equipment or services from:
- Huawei Technologies Company
- ZTE Corporation
- Hytera Communications
- Hangzhou Hikvision Digital Technology Company
- Dahua Technology Company

This notice is provided in compliance with Section 889 of the 2019 NDAA.

**Signed-off-by: Yachay <yachay@szlholdings.ai>**  
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
