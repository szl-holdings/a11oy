# Spec 05: Doctrine-Gated Certificate Enrollment

**Invention 5 of 7**  
**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17`  
**Status:** Design-complete · Implementation pending

---

## 1. Peat's Enrollment Model

Peat enrollment requires:
1. Node generates Ed25519 keypair
2. Node computes `NodeID = SHA-256(pubkey)`
3. Node submits CSR to peat-gateway with `HMAC-SHA256(formation_key, NodeID || timestamp)`
4. peat-gateway verifies HMAC, issues X.509 certificate signed by Formation CA

Anyone with the formation key can enroll. Doctrine version is not part of the enrollment proof.

---

## 2. SZL-MESH Enrollment Extension

SZL-MESH extends the enrollment CSR with three additional mandatory claims:

```json
{
  "node_id": "<SHA-256-of-Ed25519-pubkey>",
  "formation_key_proof": "HMAC-SHA256(formation_key, node_id || timestamp_utc)",
  "timestamp_utc": "<ISO-8601>",
  "doctrine_claim": {
    "doctrine_version": "749/14/163",
    "kernel_commit": "c7c0ba17",
    "slsa_level": "L1"
  },
  "section_889_attestation": {
    "vendor_exclusion_confirmed": true,
    "hardware_vendor": "<self-reported vendor string | null>",
    "attestation_method": "self_report | tpm_quote | none"
  }
}
```

The `doctrine_claim` fields are included in the HMAC proof:

```
formation_key_proof = HMAC-SHA256(
  key = formation_key,
  message = node_id || timestamp_utc || doctrine_version || kernel_commit
)
```

This cryptographically binds the doctrine claim to the enrollment proof — the node cannot claim one doctrine version in the CSR and operate under another.

---

## 3. peat-gateway Validation Steps (SZL Extension)

When a SZL-MESH peat-gateway instance receives an enrollment request:

```
1. Verify formation_key_proof (existing peat step)
2. Assert timestamp_utc is within ±5 minutes of gateway UTC clock
3. Assert doctrine_claim.doctrine_version == "749/14/163"       ← NEW
4. Assert doctrine_claim.kernel_commit == "c7c0ba17"             ← NEW
5. Assert doctrine_claim.slsa_level == "L1"                      ← NEW
6. Check node_id against revocation list (CRDT document)         ← NEW
7. Check section_889_attestation.vendor_exclusion_confirmed      ← NEW
8. If all pass: issue Node Certificate (X.509, 90-day TTL)
                signed by Formation CA (Ed25519 key)
9. Add Node Certificate to CertificateStore CRDT document
10. Return certificate to enrolling node
```

Steps 3–7 are new SZL-MESH additions. A failure at any step rejects enrollment.

---

## 4. Certificate Authority Hierarchy

```
SZL Root CA (offline, air-gapped, Ed25519)
  └── SZL Formation CA (online per-formation, Ed25519, issued by Root CA)
        └── Node Certificates (Ed25519, 90-day TTL, issued by Formation CA)
```

The Root CA private key is kept offline. Formation CAs are generated during pre-deployment ceremonies and shipped in the Zarf component alongside the formation key. The Formation CA certificate is verified against the Root CA by all nodes at startup.

---

## 5. Doctrine-Version Lifecycle

When governance doctrine increments (e.g., new NDAA provision, new Section 889 vendor):

1. New doctrine version `X/Y/Z` is issued
2. New Formation CA is generated with `doctrine_version = "X/Y/Z"` baked into the enrollment validation logic
3. Nodes running old doctrine `749/14/163` attempt enrollment and **fail step 3** above
4. Old-doctrine nodes are automatically classified as OBSERVED (peat-compatible) — no explicit revocation required
5. New formations are established with the new Formation CA and new doctrine version

This encodes the governance lifecycle in the cryptographic enrollment proof without requiring manual node-by-node revocation.

---

## 6. Section 889 Vendor Exclusion

Section 889 of the FY2019 NDAA prohibits use of telecommunications equipment from exactly 5 covered vendors:

```
1. Huawei Technologies Co., Ltd.
2. ZTE Corporation
3. Hytera Communications Corporation Limited
4. Hangzhou Hikvision Digital Technology Co., Ltd.
5. Dahua Technology Co., Ltd.
```

SZL-MESH checks the enrollment CSR's `section_889_attestation`:
- If `hardware_vendor` matches any of the 5 vendors, enrollment is rejected with reason `SECTION_889_VIOLATION`
- If `attestation_method == "none"`, the attestation is logged but enrollment proceeds (physical deployment layer controls assumed)
- If `attestation_method == "tpm_quote"` (future capability), the TPM quote is verified against a trusted endorsement key

---

## 7. Enrollment Attack Mitigations

| Attack | Mitigation |
|--------|------------|
| Unauthorized enrollment (no formation key) | HMAC proof requires formation key — infeasible without physical chain access |
| Replay enrollment (captured CSR) | Timestamp window: CSR with timestamp > 5 minutes old is rejected |
| Duplicate NodeID enrollment | peat-gateway checks CertificateStore CRDT for existing NodeID |
| Doctrine version spoofing | Doctrine version is inside the HMAC message — cannot be altered without formation key |
| CA impersonation (rogue gateway) | Nodes verify Formation CA against Root CA certificate (shipped in Zarf component) |
| Section 889 hardware attestation bypass | Best-effort; physical deployment controls are primary enforcement layer |

---

## 8. CertificateStore CRDT

Enrolled node certificates are stored in a formation-scoped CRDT document:

```json
{
  "certificates": {
    "<node_id>": {
      "cert_der": "<base64-DER-encoded-X.509>",
      "enrolled_at": "<ISO-8601>",
      "expires_at": "<ISO-8601>",
      "doctrine_version": "749/14/163",
      "kernel_commit": "c7c0ba17"
    }
  }
}
```

CRDT document ID: `"szl-mesh/certs/formation-<formation_id>"`

All enrolled nodes see all peer certificates via CRDT sync. New nodes receive the certificate store as part of initial CRDT sync — no separate certificate distribution mechanism needed.

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem)*  
*References: [BYZANTINE_HANDLING.md §4](https://github.com/szl-holdings/szl-mesh) · [peat enrollment](https://github.com/defenseunicorns/peat) · [Section 889 FY2019 NDAA](https://www.acquisition.gov/FAR/52.204-25)*
