# Forecast a governance trajectory

**id:** `recipe-forecast-trajectory`  
**tags:** forecast, pac-bayes, governance, trajectory, meridian, predict, risk  

## Summary
Run a PAC-Bayes governance trajectory forecast (Meridian) for a planned change.

## Steps
1. POST the scenario to the forecast fabric.
2. PAC-Bayes bounds returned (honest interval, not a point claim).
3. Use to gate a risky change.

## Code
```python
from szl_forecast import trajectory
band = trajectory(scenario)  # PAC-Bayes interval
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._