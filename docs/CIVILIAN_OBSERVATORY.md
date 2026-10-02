# Civilian Observatory integration

FACT: The candidate adds the `/civilian/` interface and reserves `/api/a11oy/v1/civilian/` in the existing a11oy Python application. The taxonomy home is services: public observations, source provenance, and non-effecting review.

## Data and behavior

- FACT: The readers fetch public [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog), [FIRST EPSS](https://www.first.org/epss/faq), and [NWS alerts](https://www.weather.gov/documentation/services-web-api). Source timestamps, hashes, unavailable values, and stale fallbacks remain visible.
- FACT: The repository view is a dated public-only structural snapshot, not live CI or a complete source-security review. Neither a public advisory nor a source score establishes exposure in SZL's environment.
- FACT: Root-page web-header observations admit only `a-11-oy.com` and `szlholdings.com`; HTTPS, public-address, same-host redirect, size, and timeout checks remain in the reader. There are no port, exploit, login, arbitrary-URL, or device-control operations.
- FACT: All APIs in this namespace accept GET only. Other methods return 405, unknown operations return 404, and a failed package remains unavailable rather than falling through to the parent SPA.
- FACT: The SQLite cache contains only public observations, retains original observation timestamps across failures, and caps dynamic cache entries. It is rebuildable, not a signed decision ledger or durable analyst record.
- FACT: Source refresh occurs on demand with a one-hour normal interval and a one-minute retry floor. Shared SQLite budgets cap admitted observation starts, and concurrent observers use per-key leases.
- FACT: A new runtime starts with unavailable sources and null observation hashes/timestamps until an actual public fetch completes. No frozen KEV/EPSS snapshot or training fixture is distributed in the runtime package.
- FACT: The response planner is a deterministic simulation with zero external action adapters. It does not authenticate a reviewer, create a ticket, change a firewall, control a device, or execute a research experiment.

## Packaging and tests

FACT: The runtime package and its static interface are bound by `PAYLOAD_MANIFEST.json`; this is an unsigned byte-integrity manifest, not independent execution attestation. The canonical Dockerfile includes the package and root registration shim, so the existing Dockerfile-derived `hf-sync.yml` remains the only automatic Space publisher.

FACT: No DNS, branch-protection, operator-authentication, signing-key, model-weight, or model-release-gate setting is changed by this integration. Deployment and a matching live source revision must be observed separately from a successful test run.

PROPOSAL: Run:

```sh
python scripts/build_civilian_manifest.py --check
python -m pytest tests/test_civilian_observatory.py -q
python -m pytest tests/test_demo_critical_routes.py -q
```

FACT: Interface source and its own lockfile live under `web/civilian-observatory/`; that build does not require building the broader monorepo-dependent `web/` application. CI rebuilds and compares the committed static files.

FACT: The UI separates dependency code from authored application code. The exact content-hashed dependency chunk has a narrow doctrine text-scan exception for technical library identifiers, not product claims; the build rejects authored modules in that chunk. No source-code, application-copy, or API-policy exception is introduced.

## Runtime readback

PROPOSAL: After the protected merge and canonical publisher finish, inspect `/civilian/`, `/api/a11oy/v1/civilian/health`, and `/api/a11oy/v1/civilian/overview` on both the HF origin and the product origin. Confirm JSON types, actual source times, no model/effectors, and the expected GitHub revision; an HTML 200 is not an API success.

BLOCKED: No claim of government accreditation, a new trained model, scientific model validity, or full estate qualification is made. Wider assessment scopes and real-world response adapters require their own authorization and qualification.
