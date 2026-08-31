# AGENTS.md

## Cursor Cloud specific instructions

### Repository overview

This workspace contains three repos. Only **amaru** has runnable code; the other two (`carlota-jo`, `counsel`) are documentation/specification-only at alpha stage.

### Amaru sidecar (Python FastAPI backend) — the primary service

- **Location:** `sidecar/`
- **Install:** `pip install -e ".[dev]"` from `sidecar/`
- **Run server:** `python3 -m uvicorn amaru.app:app --host 0.0.0.0 --port 6810` from `sidecar/`
- **Run tests:** `python3 -m pytest tests/ -v` from `sidecar/`
- **Lint:** `ruff check src/ tests/` from `sidecar/` (ruff must be installed separately: `pip install ruff`)

### Top-level wiring tests

- **Location:** `tests/test_chakana_wiring.py`
- **Run:** `PYTHONPATH=src python3 -m pytest tests/test_chakana_wiring.py -v` from the repo root
- The test imports `chakana_wiring` from `src/chakana_wiring.py`; you must set `PYTHONPATH=src` or pytest won't find the module.

### Web frontend (standalone)

- **Location:** `web/`
- **Install:** `npm install` from `web/`
- **Run dev server:** `VITE_PORT=5300 BASE_PATH=/ API_TARGET=http://localhost:6810 npx vite --host 0.0.0.0` from `web/`
- **Build:** `npm run build` from `web/` (outputs to `web/dist/`)
- The frontend uses stub modules in `web/src/_stubs/` for all workspace packages that originally came from the parent platform monorepo. These stubs provide fully functional implementations.
- The Vite dev server proxies `/api/amaru/*` to the FastAPI backend at `API_TARGET`.

### Hugging Face Spaces deployment

- **Deploy script:** `deploy/huggingface/deploy.sh`
- Requires `HF_TOKEN` env var. Usage: `HF_TOKEN=hf_xxx bash deploy/huggingface/deploy.sh [space-name]`
- Builds both frontend and backend into a single Docker container serving on port 7860.

### Gotchas

- `pip install` puts scripts in `~/.local/bin` which may not be on PATH. Either use `python3 -m <tool>` or `export PATH="$HOME/.local/bin:$PATH"`.
- The `huklla-7` tripwire (bus publish) will always show `warn` when running locally — the yawar-bus (Prism Bus) is a separate external service and is not expected to be available.
- DCO sign-off (`git commit -s`) is enforced by CI on all commits.
