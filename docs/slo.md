# Service Level Objectives (SLO)

**Service:** a11oy  
**Version:** v1.0.0  
**Last reviewed:** 2026-06-09  
**Next review:** 2026-09-09 (quarterly)

---

## Availability SLO

| Metric | Target | Measurement Window |
|---|---|---|
| Availability (uptime) | 99.5% | Rolling 30 days |
| Error rate | < 1% of requests | Rolling 24 hours |
| Error budget | 0.5% = ~216 minutes/month | Monthly |

---

## Latency SLOs

| Endpoint | p50 | p95 | p99 |
|---|---|---|---|
| `/api/health` | < 50ms | < 200ms | < 500ms |
| `/api/v4/*` (read) | < 200ms | < 800ms | < 2000ms |
| `/api/v4/*` (write) | < 500ms | < 2000ms | < 5000ms |

---

## Error Budget Policy

| Burn Rate | Window | Action |
|---|---|---|
| > 2× | 1 hour | Page on-call immediately |
| > 5× | 5 minutes | Incident declared; rollback considered |
| Budget exhausted | — | Freeze non-critical deploys until budget recovered |

---

## Alert Thresholds

```yaml
# Recommended alert rules (adapt to monitoring stack)
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
  for: 5m
  labels:
    severity: warning

- alert: P95LatencyBreach
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.8
  for: 10m
  labels:
    severity: warning

- alert: ServiceDown
  expr: up == 0
  for: 2m
  labels:
    severity: critical
```

---

## Observability Coverage

- [x] `/api/health` endpoint returning `{"status": "ok", "sovereign": true}`
- [x] OpenTelemetry `traceparent` W3C header propagation
- [ ] RED metrics dashboard (Rate/Errors/Duration) — post-v1.0 milestone
- [ ] Synthetic uptime monitoring — post-v1.0 milestone

---

## Sources

- [Google SRE — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- [Datadog SLOs](https://docs.datadoghq.com/service_management/service_level_objectives/)
- [Google SRE — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)

*Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>*
