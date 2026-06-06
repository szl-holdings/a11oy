# Replay yesterday's decisions

**id:** `recipe-replay-day`  
**tags:** replay, ayni, event-sourcing, reflection, audit, day, timeline, memory  

## Summary
Event-sourced AYNI replay of a day's signed decisions for self-reflection / audit.

## Steps
1. GET the AYNI run-ledger for the date.
2. Replay events in order; each carries a signed receipt.
3. Summarize decisions + outcomes.

## Code
```python
from szl_ayni import replay
timeline = replay(date='2026-05-31')
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._