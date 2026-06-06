# Advise on calendar / email (aide vertical)

**id:** `recipe-calendar-advise`  
**tags:** calendar, email, m365, advise, connector, aide, schedule  

## Summary
Read connected M365 calendar/email (advisory only) and propose actions Rosie can sign before sending.

## Steps
1. Connect M365 (read-only advisory).
2. Rosie proposes a draft action.
3. User approves; Rosie signs + acts.

## Code
```python
from szl_connectors import m365
events = m365.calendar(read_only=True)
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._