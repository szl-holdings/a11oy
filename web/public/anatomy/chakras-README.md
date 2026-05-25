# AMARU Activation Spine — 7-Chakra Ladder

The AMARU kernel is structured as a seven-layer activation spine, each layer mapped to a traditional chakra position and assigned a Quechua name. Together they form a complete cycle: sensory dispatch at the root, semantic retrieval in the sacral, generative proposal in the solar plexus, critical reflection in the heart, state commitment in the throat, tool-invocation at the third eye, and sovereign allegiance at the crown. Each chakra owns exactly one ≤10-line Python kernel derived from a publicly-licensed leader; all kernels produce byte-identical output across five independent replays.

## Chakra 1 — Root · CH'ULLA-KALLPA

The root chakra governs compute dispatch. Its kernel absorbs the device-selection primitive from tinygrad (MIT), replacing the first-available heuristic with a Butler-Volmer energy-cost weighting across four execution paths: CPU, GPU, QUANTIZED, and MOE. Given an overpotential signal per path, KALLPA selects the minimum-energy route — the body's first instinct before any cognition begins. Leader: `tinygrad/tinygrad` @ `1b779a9`.

## Chakra 2 — Sacral · CH'ULLA-YACHAY

The sacral chakra governs semantic retrieval. Its kernel distills the cosine-similarity retrieval primitive from DSPy's embeddings module (MIT) into a dual-store lookup: `pirwa_store` for feature vectors and `codex_store` for prior knowledge. Given a query, YACHAY returns the top-k feature IDs and the top-8 codex priors — the system's memory access before reasoning begins. Leader: `stanfordnlp/dspy` @ `da1f087`.

## Chakra 3 — Solar Plexus · CH'ULLA-RIMAY

The solar plexus chakra governs proposal generation. Its kernel absorbs the multinomial sampling primitive from vLLM's v1 sampler (Apache-2.0), blending feature vectors and codex priors into a softmax distribution and drawing a single token proposal with a fixed seed. RIMAY is the system's assertive voice — it produces the candidate action before any critique is applied. Leader: `vllm-project/vllm` @ `6548560`.

## Chakra 4 — Heart · CH'ULLA-YUYAY

The heart chakra governs critique and multi-axis gating. Its kernel absorbs the reflexive critique pattern from DSPy SIMBA (MIT), scoring a proposal across nine axes (cleanliness, horizon, resonance, frustum, gaussClosure, invariance, moralGrounding, ontologicalGrounding, measurabilityHonesty) and applying a conjunctive AND gate. Only proposals that clear all nine thresholds — including the stricter 0.95 bar for moralGrounding and measurabilityHonesty — proceed downstream. Leader: `stanfordnlp/dspy` SIMBA @ `da1f087`.

## Chakra 5 — Throat · CH'ULLA-RUWAY

The throat chakra governs state commitment. Its kernel absorbs the receipt-chain primitive from the OpenAI Agents Python SDK (MIT), computing a SHA-256 continuum hash over `(state, proposal, critic)` and merging a gate-cleared proposal into the running state. If the heart gate fails, RUWAY returns the original state unchanged — nothing is spoken without the heart's approval. Leader: `openai/openai-agents-python` @ `656baf8`.

## Chakra 6 — Third Eye · CH'ULLA-NAWI

The third eye chakra governs boundary-crossing tool invocation. Its kernel distills the MCP tool-dispatch primitive from the Model Context Protocol Python SDK (MIT) into a keyword-overlap ranker that selects the best-matching tool from a list, constructs argument stubs, and invokes it through an injectable `invoke` callable. TINKUY is the system's outward perception layer — its interface to the world beyond the spine. Leader: `modelcontextprotocol/python-sdk` @ `161834d`.

## Chakra 7 — Crown · CH'ULLA-HATUN

The crown chakra governs sovereign allegiance. Unlike the six layers below it, HATUN has no upstream leader — it is wholly original doctrine (Decision D45). Its kernel computes a continuum hash over the full cycle `(prev_hash, state, proposal, critic_result, timestamp)` and evaluates ten HUKLLA tripwires (T01–T10). Any single tripwire firing freezes state advancement; only Stephen can reset. The crown never stops computing the receipt chain — but it can stop the world from moving forward.
