# Run the Warhacker demo

**id:** `recipe-warhacker-demo`  
**tags:** warhacker, demo, run, k3d, uds, pepr, dsse, readiness, defense  

## Summary
Execute the Warhacker readiness demo (k3d + uds-cli + Pepr DSSE) — San Diego June 16-19 2026, readiness 6/6 GREEN.

## Steps
1. Confirm 6/6 GREEN readiness gates.
2. Bring up k3d cluster; deploy via uds-cli; Pepr admission signs each apply with DSSE.
3. Verify the signed admission receipts.

## Code
```python
# Warhacker demo (San Diego, June 16-19 2026)
# k3d cluster up -> uds-cli deploy -> Pepr DSSE admission
bash scripts/warhacker_demo.sh  # readiness 6/6 GREEN
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._