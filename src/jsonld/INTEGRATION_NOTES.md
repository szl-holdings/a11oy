# W3C JSON-LD Verifiable Credentials Integration Notes

## Standards Compliance
- **W3C VC Data Model 2.0**: https://www.w3.org/TR/vc-data-model-2.0/
- **JSON-LD 1.1**: https://www.w3.org/TR/json-ld11/
- **IETF SCITT**: https://datatracker.ietf.org/wg/scitt/documents/
- **eIDAS 2.0 ARF**: https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework

## Integration with Existing Organs

### After Rekor submission (capability 1)
```typescript
// In organ emitReceipt() pipeline:
const rekorResult = await submitDSSEToRekor(envelope, rekorOpts);
const augmentedReceipt = augmentReceiptWithRekor(receipt, rekorResult);
const vc = wrapDSSEinVC(augmentedReceipt, { signingKeyPem: ... });
await pinToIPFS(serializeVC(vc));  // capability 3
```

### MCP tool: `get_receipt_vc`
New MCP tool that returns the W3C VC form of any receipt by ID:
```typescript
server.tool("get_receipt_vc", { receiptId: z.string() }, async ({ receiptId }) => {
  const receipt = await lookupReceipt(receiptId);
  const vc = wrapDSSEinVC(receipt);
  return { vc: JSON.parse(serializeVC(vc)) };
});
```

### EU eIDAS 2.0 / EUDIW ARF path
The `SZLGovernanceReceipt` VC type can be presented to EUDIW-compatible wallets
that accept W3C VC 2.0 credentials.  The `validFrom` / `validUntil` fields map
directly to the EUDIW attestation lifecycle model (ARF §6.6.2).

### IETF SCITT
`wrapForSCITT()` produces a VP envelope suitable for submission to an IETF SCITT
transparency service (draft-ietf-scitt-architecture §5.1 "Signed Statement").
The `SZLGovernanceAuditPresentation` type signals to SCITT verifiers that this
is a governance audit trail, not a product artifact.

### US DoD CMMC / NIST SP 800-218
The `policyRef` and `doctrineVersion` fields in `credentialSubject` map to CMMC
Practice AC.3.021 (audit log protection) and NIST SP 800-218 §2.2
(supply chain risk management attestation).

## Production Cryptosuite Upgrade
Replace `DSSESignature2024` with `ecdsa-rdfc-2022` using:
```
npm install @digitalbazaar/ecdsa-rdfc-2022-cryptosuite
npm install @digitalbazaar/vc
```

The `@digitalbazaar/vc` library handles full RDF Dataset Normalization (URDNA2015)
required by the `ecdsa-rdfc-2022` spec, replacing our RFC 8785 approximation.

## Context URL Hosting
The `receipt_context.json` file must be hosted at:
`https://szl.io/ns/receipt/v1/context.json`

Until then, it can be embedded inline as a JSON-LD context object in the
`@context` array (replace the URL string with the parsed object).
