# GDW operational benchmarks

These commands produce run-specific evidence. They do not establish a universal
throughput or production-scale claim.

```powershell
$env:GDW_AUTH_TOKEN = 'local-only-token'
$env:GDW_PROOF_EXPORT_MODE = 'outbox'
# Full integration target:
python -m uvicorn serve:app --host 127.0.0.1 --port 8080
# Isolated throughput target, same production router:
python -m uvicorn benchmarks.gdw.bench_app:app --host 127.0.0.1 --port 8080
python benchmarks/gdw/burst_client.py --total 10000 --concurrency 250
python benchmarks/gdw/dashboard_export.py
python benchmarks/gdw/kda_mla_memory_bench.py --device cuda
python benchmarks/gdw/drain_proof_outbox.py --limit 1000
```

Use `--shared-session shared-burst` on the burst client to stress serialized
same-session transitions and SQLite contention. Raw JSON, CSV, summary JSON,
offline HTML, and checksums are written under `output/bench_results/`.
`outbox` mode atomically persists every theorem input with the transition and
lets the drain export files outside the write transaction. `sync` mode remains
the default for low-volume operator validation.
