# AGENTS.md

## Cursor Cloud specific instructions

This is the **SZL Brand SDK** — a proper Python package for deterministic brand asset generation, validation, and governance.

### Quick reference

```bash
# Install the package (editable, with dev dependencies)
pip install -e ".[dev]"

# CLI entry point
python3 -m szl_brand --help
szl-brand --help

# Generate all 14 social previews
szl-brand generate -o social-previews

# Generate a custom preview
szl-brand generate-one --repo my-repo --title "Title" --subtitle "Sub" -o out.png

# Validate assets (dimensions, integrity)
szl-brand validate social-previews

# Generate SHA-256 integrity manifest
szl-brand manifest social-previews -o brand-manifest.json

# Check drift against manifest
szl-brand drift --manifest brand-manifest.json social-previews

# Show inventory
szl-brand inventory social-previews

# Start live gallery server (port 8742)
szl-brand serve
```

### Running tests & lint

```bash
python3 -m pytest tests/ -v       # 49 tests
ruff check src/ tests/            # lint
ruff format --check src/ tests/   # format check
```

### Key dependencies

- **Python 3.12** — required runtime
- **Pillow** — PNG banner generation (procedural generative engine)
- **ReportLab** — PDF anatomy figure generation
- **poppler-utils** (`pdftoppm`) — PDF→PNG conversion for anatomy scripts
- **DejaVu fonts** — text rendering at `/usr/share/fonts/truetype/dejavu/`
- **Ruff** — lint/format
- **pytest** — test suite

### Non-obvious caveats

1. **Anatomy scripts write to hard-coded absolute paths** outside the repo. Create these before running `rebuild_all.sh`:
   ```bash
   sudo mkdir -p /home/user/workspace/field_meditation
   sudo mkdir -p /home/user/workspace/evolution_pod/finish/anatomy/figures
   sudo chmod -R 777 /home/user/workspace
   ```
2. **`build_explainer_pdfs.py`** requires markdown source files from external paths — expected to fail in isolation.
3. **The `social-previews/gen.py` script is the legacy generator.** The new SDK (`python3 -m szl_brand generate`) is the canonical way to generate previews.
4. **Procedural generation is deterministic** — same repo name always produces identical output (seeded by SHA-256 of repo name).
