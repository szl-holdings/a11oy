# HMAC Key Handling — szl-receipts

## Summary

The `server.hmacKey` value in `charts/szl-receipts/values.yaml` **must be a raw (plaintext) string**, not a base64-encoded value.

## Why

The Helm chart template in `charts/szl-receipts/templates/service.yaml` applies `b64enc` to the value when writing it to the Kubernetes Secret:

```yaml
hmac-key: {{ .Values.server.hmacKey | b64enc | quote }}
```

Kubernetes Secrets store values as base64. If you pre-encode the value in `values.yaml`, the secret will contain double-encoded bytes:

- `values.yaml` → `"c3ps..."` (base64 of the raw key)
- Template applies `b64enc` → `"YzNwc..."` (base64 of the base64)
- Pod reads secret and base64-decodes → gets ASCII bytes of the first base64 string, not the original key
- HMAC verification fails for all receipts

## Correct pattern

```yaml
# charts/szl-receipts/values.yaml  ← store the raw string here
server:
  hmacKey: "szl-dev-demo-key-2026-warhacker"   # raw string, NOT base64
```

```yaml
# charts/szl-receipts/templates/service.yaml  ← b64enc applied once here
data:
  hmac-key: {{ .Values.server.hmacKey | b64enc | quote }}
```

## Production key injection

In production, do **not** store the key in values.yaml. Inject it via:

1. **UDS bundle variable** (recommended):
   ```yaml
   # uds-bundle.yaml
   variables:
     - name: RECEIPT_HMAC_KEY
       path: server.hmacKey
       sensitive: true
   ```
   Then deploy with:
   ```bash
   uds deploy uds-bundle-szl-receipts.tar.zst --set RECEIPT_HMAC_KEY="$(cat /path/to/key)"
   ```

2. **External secret operator** (production clusters): Use ESO to pull the key from Vault or AWS Secrets Manager and inject it as a Kubernetes Secret directly, bypassing the Helm chart secret entirely.

## Key rotation

After rotating the HMAC key:
1. Update the Kubernetes Secret `szl-receipts-hmac` in namespace `szl-receipts`
2. Restart the `szl-receipts-server` deployment: `kubectl rollout restart deployment/szl-receipts-server -n szl-receipts`
3. Update the `szl.io/rotate-before` annotation in `charts/szl-receipts/templates/service.yaml`

## Reference

- [Kubernetes Secrets encoding](https://kubernetes.io/docs/concepts/configuration/secret/#overview-of-secrets)
- [Helm b64enc function](https://helm.sh/docs/chart_template_guide/function_list/#b64enc)
- Fix committed in PR #perplexity/uds-p0-blockers-2026-05-30 (MF-5)
