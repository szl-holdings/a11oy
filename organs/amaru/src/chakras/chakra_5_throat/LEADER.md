# LEADER: openai/openai-agents-python

## Selection

**Chosen:** `openai/openai-agents-python`  
**License:** MIT (verified at SHA `656baf8ead8c970529d2c935acecac70ddc4fdc9`)  
**Repo:** https://github.com/openai/openai-agents-python  
**Last push:** 2026-05-14

## License Verification

```
gh api repos/openai/openai-agents-python --jq '.license.spdx_id'
→ "MIT"
```

License file confirmed at repo root. MIT is unambiguously permissive (Apache-2.0 / MIT / BSD compliant per DOCTRINE).

## Execute Core Read

Core execution lives in `src/agents/run.py` (commit `656baf8`).  
Pattern: `Runner.run(agent, input)` → iterates turns → calls model → resolves tool outputs → returns `RunResult`.  
The loop is: receive state, apply proposal (tool/model call), gate on guardrails, emit result.

This maps directly onto the RUWAY pattern: `(state, proposal, gate_pass) → new_state + receipt`.

## Why Not E2B

E2B (`e2b-dev/E2B`, Apache-2.0, SHA `9e962ae`) is also valid. It was rejected because its execute core (`sandbox.commands.run()`) is infrastructure-level (spawns a cloud process via gRPC), making it heavier and less portable as a pure kernel pattern. The openai-agents-python `Runner` loop is a cleaner state-transition model.
