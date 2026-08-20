# GDW operational benchmarks

These commands produce run-specific evidence. They do not establish a universal
throughput or production-scale claim.

```powershell
$token = 'local-only-benchmark-token'
$tokenSha = [System.BitConverter]::ToString(
  [System.Security.Cryptography.SHA256]::HashData(
    [System.Text.Encoding]::UTF8.GetBytes($token)
  )
).Replace('-', '').ToLowerInvariant()
$env:GDW_PRINCIPALS_JSON = "{`"benchmark-operator`":{`"token_sha256`":`"$tokenSha`",`"roles`":[`"user`",`"admin`"]}}"
$env:GDW_BENCH_TOKEN = $token
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

`GDW_BENCH_TOKEN` is only a client input. The service accepts a bounded
`GDW_PRINCIPALS_JSON` registry of token digests and roles; it does not use a
single global bearer token.

Use `--shared-session shared-burst` on the burst client to stress serialized
same-session transitions and SQLite contention. Raw JSON, CSV, summary JSON,
offline HTML, and checksums are written under `output/bench_results/`.
`outbox` mode atomically persists the transition, deterministic local receipt,
and receipt/proof projection records, then lets a leased drain export
immutable, owner-scoped, generation-bound files outside the write transaction.
`sync` mode is rejected because an external write before SQLite commit can
orphan or duplicate evidence. Requests with non-exported effects are retained
fail-closed when retention expires.
