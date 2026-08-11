# Operations

## Local verification

```bash
python -m compileall -q src tests tools
pytest -q
alloy-council canary --workdir /tmp/council-canary-a --output /tmp/canary-a.json
alloy-council canary --workdir /tmp/council-canary-b --output /tmp/canary-b.json
cmp /tmp/canary-a.json /tmp/canary-b.json
alloy-council bench --output /tmp/bench-a.json
alloy-council bench --output /tmp/bench-b.json
cmp /tmp/bench-a.json /tmp/bench-b.json
python tools/generate_protocol_schemas.py
python tools/validate_schemas.py
python tools/static_secret_scan.py . --output /tmp/secret-scan.json
python tools/verify_action_pins.py .github/workflows --output /tmp/action-pins.json
node --check src/szl_council_kernel/web/app.js
```

## Backup

Stop mutations, checkpoint WAL, copy the SQLite database and signer public metadata, hash the copies, and register the backup digest in an external retention system. Never copy a private key into an evidence bundle.

## Recovery

Restore the database, run `verify-ledger`, verify the last externally anchored checkpoint, reconcile any provider actions that were in flight, and do not retry an ambiguous external attempt automatically.

## Key rotation

Create a new managed key, publish a signed transition, retain old public keys for historical verification, switch only after policy approval, and verify both pre- and post-rotation receipts. Local raw key files are a development mechanism, not a production custody design.

## Container build boundary

The default development image is a floating convenience tag. Production builds must pass an independently reviewed immutable digest, for example:

```bash
docker build \
  --build-arg PYTHON_IMAGE=python:3.13-slim@sha256:<reviewed-digest> \
  -t szl-council-kernel:0.5.0rc1 .
```

Record the exact base-image digest, wheel digest, source revision, policy revision, and deployment digest in the release evidence.
