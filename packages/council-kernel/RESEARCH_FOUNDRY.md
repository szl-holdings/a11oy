# Research Foundry

The Research Foundry is an admission and promotion boundary for external technical inputs. It does not scrape or execute remote repositories.

A caller may normalize GitHub, GitLab, arXiv, or publication content into a `ResearchSource` only after binding:

- source kind and URI;
- immutable revision;
- SHA-256 content identity;
- retrieval time;
- explicit rights status;
- license expression when policy requires one.

GitHub and GitLab records require a full commit hash. arXiv records require a versioned identifier such as `2406.04692v2`. This prevents a mutable branch, tag, or unversioned paper reference from silently changing the research basis.

Every admitted `ResearchArtifact` begins in `QUARANTINED`, including artifacts that appear to satisfy all gates. A separate promotion evaluation checks rights, license, evidence count, extracted claims, and reproduction state. The result is `ELIGIBLE` or `BLOCKED`; it does not install code, train a model, change a policy, or execute an action.

Admissions and evaluations are appended to the same hash-chain ledger contract used by the Council kernel. Bundle digests are order-independent so a source set can be compared across ingestion paths.

Network retrieval, malware analysis, license interpretation, sandbox execution, benchmark execution, and final production promotion remain separate controlled services.
