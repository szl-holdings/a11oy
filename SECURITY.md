<!-- VENDORED FROM szl-holdings/platform@de08cf8ec5836b0cef968d6560a92ecbd1bc6f4b — SECURITY.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
# Security Policy

The rationale for every active secret-scanner suppression is generated at
[security/ALLOWLIST-JUSTIFICATIONS.md](security/ALLOWLIST-JUSTIFICATIONS.md).

## Supported versions

Security fixes are developed against the current protected default branch and,
when a release is published, the most recent maintained release line. Older
releases may receive a backport when the risk, exploitability, and patch
complexity justify it. A version is not supported merely because it remains
available in Git history, a package registry, a container registry, or a mirror.

## Report a vulnerability

**Do not open a public issue, discussion, or pull request for a suspected
vulnerability.**

Use the repository's **Security → Report a vulnerability** form when it is
available. That private GitHub advisory is the preferred channel because it
keeps reproduction details, patches, and coordination inside the repository's
confidential security workspace.

When private reporting is unavailable, email **security@szlholdings.com**. Include
only the information needed to reproduce and assess the issue:

1. affected component, version, commit, image, model, dataset, or endpoint;
2. minimal reproduction steps or proof of concept;
3. expected and observed behavior;
4. impact and realistic attack preconditions;
5. suggested mitigation, when known;
6. a safe way to contact the reporter.

Do not include live credentials, customer data, private keys, access tokens, or
regulated data. Replace them with synthetic values and describe how the
maintainer can reproduce the condition safely.

## Triage and disclosure targets

The following are **best-effort operating targets**, not contractual service
levels. A one-maintainer project may need to contain an issue before a complete
fix is available, and resolution time depends on exploitability, upstream
coordination, release risk, and the ability to verify a safe rollback.

| Severity | Acknowledgement target | Initial triage target |
|---|---:|---:|
| Critical | 1 business day | 2 business days |
| High | 2 business days | 5 business days |
| Medium | 5 business days | 10 business days |
| Low | 10 business days | 20 business days |

The maintainer will coordinate disclosure timing with the reporter and affected
upstreams. Ninety days is a coordination goal, not an automatic publication
deadline. Earlier disclosure may be appropriate after a verified fix is
available; additional time may be appropriate when publication would materially
increase risk before users can update.

## Security-response lifecycle

1. Acknowledge the report and establish a confidential coordination channel.
2. Reproduce the issue against an exact source or artifact revision.
3. Classify severity, affected surfaces, exploit preconditions, and exposure.
4. Contain the issue and prepare the smallest safe patch in a private advisory or
   private fork when confidentiality is required.
5. Run the applicable exact-head tests, static analysis, dependency, secret,
   container, policy, provenance, and rollback gates.
6. Publish the fixed release or protected merge and any appropriate advisory.
7. Verify the deployed artifact or runtime against the fixed source revision.
8. Close the advisory only after evidence identifies what was fixed, what remains
   affected, and how to upgrade or roll back.

## Solo-operator control model

SZL Holdings currently operates this repository with one authorized maintainer.
The process must remain executable by that maintainer and does not require an
unavailable second human merely to unblock routine remediation or release work.
Separation of duties is instead provided by independent, fail-closed controls:

- protected branches and normal pull-request or merge-queue admission;
- exact-head binding and current-base checks;
- DCO trailers and protected-branch signature requirements;
- CodeQL, dependency, secret, container, policy, and regression workflows;
- immutable or digest-bound evidence where the corresponding workflow succeeds;
- explicit rollback instructions and live post-release readback.

The maintainer must not disable a gate, force-push protected history, use an
administrator merge bypass, self-approve through a bot identity, expose secret
values, or describe a merge as a deployment without deployment evidence.

## Supply-chain evidence

Supply-chain claims are revision- and workflow-specific:

- DCO and signature status are established by the protected checks and final
  protected commit, not by this document alone.
- An SBOM is release evidence only when the protected SBOM workflow succeeds and
  the resulting artifact is retained for the exact release revision.
- Build provenance or an attestation is claimed only when its protected workflow
  succeeds and the attestation can be resolved to the exact artifact digest.
- Container or package signing is claimed only when signature publication and
  verification succeed for the named digest or version.
- A green source scan does not by itself prove that a registry artifact or live
  runtime contains the same bytes; deployment and readback remain separate
  evidence boundaries.

## Section 889 statement

The project is intended not to depend on covered telecommunications equipment or
services from Huawei Technologies Company, ZTE Corporation, Hytera
Communications Corporation, Hangzhou Hikvision Digital Technology Company, or
Dahua Technology Company. This repository statement is not a substitute for a
procurement-specific legal or supplier attestation.

## Doctrine and claim boundaries

Current doctrine and proof status are defined by the repository-tracked source,
current protected checks, and generated evidence. Historical declaration,
axiom, or placeholder counts are not frozen into this policy. Lambda uniqueness
remains a conjecture unless a current, independently checkable proof artifact
establishes otherwise. This project does not claim Iron Bank, FedRAMP, CMMC, or
SWFT authorization without the corresponding external authority and evidence.

## Contact

- **Private security reports:** use **Security → Report a vulnerability** in the
  affected repository when available
- **Fallback security email:** security@szlholdings.com
- **General:** hello@szlholdings.com
- **Website:** https://a-11-oy.com

This policy follows the principles of the
[OpenSSF Vulnerability Disclosure Guide](https://github.com/ossf/oss-vulnerability-guide).
