# REJECTED CANDIDATES

## ShishirPatil/gorilla (Apache-2.0)

**Repo:** https://github.com/ShishirPatil/gorilla  
**License SHA:** `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64` — Apache-2.0 ✓ (permissive)

**Why rejected:**  
OpenFunctions inference is model-weight-coupled. The dispatch path is:
`prompt → vLLM/gorilla-openfunctions-v2 → parsed function call`.
There is no kernel-extractable pure-Python chooser; the "tool selection" is the LLM inference itself. Mocking it requires either a full HTTP stub server or monkey-patching the transformer forward pass — neither fits the ≤10-line, mockable-callable constraint. Additionally, the minimal dependency footprint includes `torch`, which is hundreds of MB. **Honest credit:** gorilla is the right choice for LLM-native tool selection at scale; it is rejected here only for kernel-size and mockability reasons, not quality.

## ToolFormer-style approaches

**Reference:** Schick et al. 2023 — "Toolformer: Language Models Can Teach Themselves to Use Tools" (https://arxiv.org/abs/2302.04761)  
**License:** No canonical Apache/MIT reference implementation exists. The closest open repo (`lucidrains/toolformer-pytorch`) is MIT-licensed but is a community reimplementation, not an authoritative dispatch library.

**Why rejected:**  
No single authoritative permissive-licensed reference implementation of the dispatch primitive. The paper's contribution is the self-supervised training method, not a reusable routing kernel. Using the community reimplementation would require citing an unofficial port. **Honest credit:** ToolFormer's API-call injection technique directly inspired MCP's tool-call framing; it is the conceptual ancestor of the chosen leader.
