# REJECTED CANDIDATES

## e2b-dev/E2B

**License:** Apache-2.0 ✓ (confirmed at SHA `9e962ae5557e88ad6e02d5d4f8da1b3f5b6c8d44`)  
**Repo:** https://github.com/e2b-dev/E2B

**Reason for rejection:**  
E2B's execute core (`sandbox.commands.run()` in `packages/python-sdk/e2b/sandbox_sync/commands/command.py`) spawns cloud processes via gRPC against a remote envd daemon. This is infrastructure-level execution, not a portable state-transition kernel. It requires API keys, network, and a live sandbox instance — incompatible with the ≤10 line, zero-dependency, byte-identical kernel requirement. The pattern does not map cleanly onto `(state, proposal, gate_pass) → new_state`.

## OpenAI Apps SDK

No distinct "OpenAI Apps SDK" public repository was found under the `openai` GitHub org as a separate entity at recon time. The current public repo for agent orchestration is `openai/openai-agents-python` (MIT), which was selected as leader. If a separate Apps SDK repo surfaces, it would need independent license verification.

## LangChain / LlamaIndex / others

Not evaluated — not listed as LEADER CANDIDATES in DOCTRINE. Recon scope was limited to the three named candidates.
