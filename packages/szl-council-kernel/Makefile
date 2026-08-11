.PHONY: test schemas canary bench verify build clean

test:
	python -m compileall -q src tests tools
	PYTHONPATH=src pytest -q

schemas:
	PYTHONPATH=src python tools/generate_protocol_schemas.py
	PYTHONPATH=src python tools/validate_schemas.py

canary:
	PYTHONPATH=src python -m szl_council_kernel.cli canary --output evidence/COUNCIL_CANARY.json --workdir evidence/runtime/canary

bench:
	PYTHONPATH=src python -m szl_council_kernel.cli bench --output evidence/COUNCIL_BENCH.json

verify: test schemas canary bench
	PYTHONPATH=src python -m szl_council_kernel.cli verify-ledger --db evidence/runtime/canary/council.sqlite3 --output evidence/LEDGER_VERIFICATION.json
	PYTHONPATH=src python tools/static_secret_scan.py . --output evidence/SECRET_SCAN.json
	PYTHONPATH=src python tools/verify_action_pins.py .github/workflows --output evidence/ACTION_PINS.json
	node --check src/szl_council_kernel/web/app.js

build:
	python -m pip wheel . --no-deps --no-build-isolation -w dist
	python -m pip wheel . --no-deps --no-build-isolation -w dist-repeat

clean:
	rm -rf build dist dist-repeat .pytest_cache src/*.egg-info evidence/runtime
