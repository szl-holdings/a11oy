# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
PYTHON ?= python3
OPA ?= opa
CEDAR ?= cedar

.PHONY: ledger test policy verify serve package
ledger:
	$(PYTHON) tools/build_ledger.py --root .. --opa "$(OPA)"
test:
	$(PYTHON) -m unittest discover -s tests -v
policy:
	$(OPA) fmt --fail policy/rego
	$(OPA) test policy/rego -v
verify:
	$(PYTHON) tools/verify.py --opa "$(OPA)" --cedar "$(CEDAR)"
serve:
	$(PYTHON) server.py --host 127.0.0.1 --port 8787
package: verify
	$(PYTHON) tools/package_release.py
