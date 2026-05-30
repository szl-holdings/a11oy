# Sigstore Rekor Integration Notes

## Connection to Existing SZL Organs

### sentra / amaru / rosie organ layer
Every DSSE receipt emitted by `emitReceipt()` in the organ layer gains a new
**side-car step**: after HMAC-signing the PAE envelope, `submitDSSEToRekor()`
is called and the returned `RekorSubmitResult` is appended to the JSONL chain
as a `rekorAttestation` block.

```jsonl
{"receiptId":"szl-2026-001","organ":"sentra","action":"deploy",...,"rekorAttestation":{"uuid":"382898f8...","logIndex":42000000,"integratedTime":1748563200,"entryUrl":"https://rekor.sigstore.dev/api/v1/log/entries/382898f8...","verifyCmd":"rekor-cli get --uuid 382898f8..."}}
```

### Pepr admission controller
`emitRekorAttestation()` is exported for use in Pepr `When().Mutate()` hooks:

```typescript
When(SZLReceipt).IsCreated().Mutate(async (receipt) => {
  const result = await emitRekorAttestation(receipt.Raw.spec.envelope, opts);
  receipt.SetAnnotation("szl.io/rekor-uuid", result.uuid);
  receipt.SetAnnotation("szl.io/rekor-integrated-time", String(result.integratedTime));
});
```

### MCP `verify_receipt` tool
Add `rekorUuid` to the `verify_receipt` tool response:

```typescript
// In MCP server tool handler:
const rekorCheck = await verifyRekorEntry(receipt.rekorAttestation.uuid, receipt.envelope.payload);
return { ...existingResponse, rekorVerified: rekorCheck.verified, rekorLogIndex: rekorCheck.logIndex };
```

## Keyless Signing (Production Path — STAGED-ADVISORY)

In GitHub Actions, replace `signingKeyPem` with Fulcio OIDC flow:

```yaml
# .github/workflows/szl-receipt.yml
- uses: sigstore/cosign-installer@v3
- run: |
    OIDC_TOKEN=$(curl -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
      "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sigstore" | jq -r .value)
    # Exchange via Fulcio:
    # POST https://fulcio.sigstore.dev/api/v2/signingCert
    # Body: { certificateSigningRequest: <CSR>, oidcIdentityToken: <token> }
```

The returned ephemeral X.509 cert from Fulcio encodes the GitHub Actions OIDC
`sub` claim (e.g. `repo:SZL-Holdings/a11oy:ref:refs/heads/main`) in its SAN,
making the signing identity cryptographically bound to the workflow run — with no
long-lived keys.

## Endpoint Reference
- Production: `https://rekor.sigstore.dev/api/v1/log/entries`
- Public key:  `https://rekor.sigstore.dev/api/v1/log/publicKey`
- Log info:    `https://rekor.sigstore.dev/api/v1/log`
- CLI verify:  `rekor-cli get --uuid <uuid> --rekor_server https://rekor.sigstore.dev`

## Dependency Chain
```
organ layer → emitReceipt() → submitDSSEToRekor() → Rekor API
                                                  ↓
                                       RekorSubmitResult appended to JSONL
                                                  ↓
                           MCP verify_receipt ← verifyRekorEntry()
```
