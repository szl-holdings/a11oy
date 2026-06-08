# SLI/SLO/Error Budget — SZL Holdings Flagship Services
**Doctrine v11 LOCKED 749/14/163 | SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap | Generated: 2026-06-03**

## Service Level Indicators (SLIs)

| Indicator | Measurement | Tool |
|-----------|-------------|------|
| Availability | % 200 responses on / and /api/health | Uptime Robot / HF Space status |
| Latency | P50, P95, P99 response time on doctrine endpoints | HF Metrics |
| Error Rate | 5xx responses / total requests | HF Logs |
| Doctrine Integrity | Correct `doctrine: v11`, `declarations: 749` in responses | Automated checker |

## Service Level Objectives (SLOs)

| Flagship | Endpoint | SLO | Window | Error Budget |
|----------|----------|-----|--------|--------------|
| a11oy | / (root) | 99.5% availability | 30-day rolling | 3.65 hours downtime |
| a11oy | /v1/lambda | 99.5% + correct doctrine | 30-day rolling | 3.65 hours |
| a11oy | /v1/honest | 99.5% + correct disclosure | 30-day rolling | 3.65 hours |
| sentra | /api/sentra/v1/lambda | 99.5% availability | 30-day rolling | 3.65 hours |
| sentra | /api/sentra/v1/verdict | 99.5% + non-empty response | 30-day rolling | 3.65 hours |
| amaru | /api/amaru/v1/brain | 99.0% availability | 30-day rolling | 7.2 hours |
| rosie | /api/rosie/v1/lambda | 99.5% availability | 30-day rolling | 3.65 hours |
| killinchu | /api/killinchu/v1/lambda | 99.5% availability | 30-day rolling | 3.65 hours |

## Notes on HF Space Constraints

SZL Holdings flagships run on HuggingFace Spaces (cpu-basic tier). Honest disclosure:
- HF free-tier spaces may sleep after 48h inactivity → cold start 30-60s
- SLO window resets if space restarts (cold start not counted as downtime if < 120s)
- Actual latency P99 may be 2-5x higher during cold start
- Error budget measured from the moment space is RUNNING

## Error Budget Policy

- If error budget is **<50% remaining**: freeze new deployments to that space
- If error budget is **exhausted**: escalate to founder; no changes until budget resets
- **SLO burn alert**: If 5% of budget consumed in 1 hour → immediate investigation

## Doctrine Compliance SLO

| Check | SLO | Measurement |
|-------|-----|-------------|
| `doctrine: v11` in all responses | 100% | Automated grep |
| `declarations: 749` | 100% | Automated check |
| `sorries_total: 163` | 100% | Automated check |
| `kernel_commit: c7c0ba17` | 100% | Automated check |
| Λ = Conjecture 1 (not theorem) | 100% | Automated check |
| SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap (not L3) | 100% | Automated check |
| Section 889 = exactly 5 vendors | 100% | Automated check |

**Signed-off-by: Yachay <yachay@szlholdings.ai>**  
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
