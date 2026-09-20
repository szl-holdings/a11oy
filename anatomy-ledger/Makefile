PYTHON ?= python3
OPA ?= $(shell command -v opa 2>/dev/null || echo /tmp/opa)
ROOT := ..

.PHONY: ledger test policy cedar verify serve package

ledger:
	$(PYTHON) tools/build_ledger.py --root $(ROOT) --opa "$$(command -v $(OPA) || true)"

test:
	$(PYTHON) -m unittest discover tests -v

policy:
	@if command -v $(OPA) >/dev/null 2>&1; then \
	  $(OPA) fmt --fail policy/rego && $(OPA) test policy/rego -v; \
	else \
	  echo "OPA unavailable; python twin tests still run via 'make test'"; \
	fi

cedar:
	$(PYTHON) -m json.tool policy/cedar/intent-auth.schema.json >/dev/null
	$(PYTHON) -m json.tool policy/cedar/entities.json >/dev/null
	$(PYTHON) -m json.tool policy/cedar/example-request.json >/dev/null
	$(PYTHON) -m json.tool policy/cedar/requests/deploy-allow.json >/dev/null
	@if command -v cedar >/dev/null 2>&1; then \
	  cedar validate --schema policy/cedar/intent-auth.cedarschema policy/cedar/intent-auth.cedar; \
	else \
	  echo "Cedar CLI unavailable; native schema + Python PARC twin still verified by tests"; \
	fi

verify: test policy cedar ledger
	$(PYTHON) -m json.tool public/data/ledger.json >/dev/null
	$(PYTHON) -m json.tool toolchain-lock.json >/dev/null
	@if [ -f $(ROOT)/docs/sovereign-control-plane-audit.json ]; then \
	  $(PYTHON) -m json.tool $(ROOT)/docs/sovereign-control-plane-audit.json >/dev/null; \
	fi

serve: ledger
	$(PYTHON) server.py --host 0.0.0.0 --port 8787

package: verify
	mkdir -p dist
	tar -czf dist/anatomy-ledger.tar.gz README.md server.py public policy tools tests Makefile toolchain-lock.json
	sha256sum dist/anatomy-ledger.tar.gz > dist/anatomy-ledger.tar.gz.sha256
