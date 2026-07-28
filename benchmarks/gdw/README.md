# GDW operational benchmarks

These commands produce run-specific evidence. They do not establish a universal
throughput or production-scale claim.

```powershell
$env:GDW_CREDENTIALS_JSON = '{"version":1,"credentials":[{"owner_id":"local-owner","namespace":"a11oy","key_id":"local-1","token":"replace-with-a-secret-managed-token","scopes":["bench:read","integrity:read","metrics:read","session:read","step:write"]}]}'
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
`outbox` mode atomically persists the transition, deterministic local receipt,
and receipt/proof projection records, then lets a leased drain export
idempotently named files outside the write transaction. `sync` mode is rejected
because an external write before SQLite commit can orphan or duplicate evidence.
The container entry point supervises bounded drain passes. On persistent
network-backed storage, use `GDW_SQLITE_JOURNAL=DELETE`,
`GDW_SQLITE_SYNCHRONOUS=FULL`, and paths contained by the verified mount.
