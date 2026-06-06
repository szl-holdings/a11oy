# Mode I — IL5/FedRAMP crypto (DOCUMENTATION ONLY)
No demo-day switch. Today HMAC (master) / Ed25519 software key (PR#19) = Tier 0.
Tier 2 (DoD-deployable) = external KMS/HSM, e.g. AWS CloudHSM hsm2m.medium
FIPS 140-3 L3 Cert #4703. ~6-8 weeks. Cross-ref docs/KEY_CUSTODY_RUNBOOK.md
(szl-uds-deployment#21). `run.sh` prints the path + exits 7.
