# INCIDENT 2026-09-01 — a-11-oy.com serving edge 404

**Detected:** 2026-09-01T04:4xZ by the mobile viewport audit (headless Chromium, three widths).
**Symptom:** `https://a-11-oy.com/` returns HTTP 404 with the Hugging Face edge 404 page on all viewports. Direct Space URL `szlholdings-a11oy.hf.space` returns 200 — **the Space runs; the custom-domain mapping is broken.**
**Cache masking:** earlier same-day fetches returned a healthy page from a third-party cache (`is_cached: true`). The outage may predate detection. Cached copies are not liveness evidence — the estate's own rule.
**Root cause (hypotheses, evidence-bound):**
1. Space-side custom-domain attachment removed/expired (HF edge has no Host mapping) — most likely.
2. Cloudflare DNS target changed away from HF edge — could not be verified: the Cloudflare connector's stored API key is malformed (X-Auth-Key 6103) pending re-auth.
**Impact:** product front door down; proof registry a11oy.net unaffected (200, byte-identical to source).
**Fix owners:** (a) HF org admin re-attaches the custom domain on Space SZLHOLDINGS/a11oy settings; (b) verify Cloudflare CNAME target after re-auth. Neither is executable with current token scopes.
**Status:** OPEN · detected-by-audit · recorded, not silently absorbed.
