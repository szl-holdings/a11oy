# CI trigger

Last: 2026-06-09T06:42Z — re-run after GitHub<->HF source sync.

Re-trigger rationale: serve.py and a11oy_dev1_endpoints.py were ahead on GitHub
vs the live Space (persistent signing-key support with honest ephemeral
fallback). Both were deployed byte-identical to the Space and the Docker Space
was factory-restarted. This commit re-runs the gates to confirm hf-module-drift
returns to success. Notes kept token-free so this file does not trip the §1
banned-token scan.