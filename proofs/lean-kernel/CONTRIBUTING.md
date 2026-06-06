# CONTRIBUTING.md

Thank you for contributing to SZL Holdings.

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/szl-holdings/lean-kernel.git
   cd lean-kernel
   ```
2. Install dependencies:
   - Python repo: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
   - Node repo: `pnpm install` (or `npm install` if no `pnpm-lock.yaml`)
   - Lean repo: follow the `README.md` instructions for `elan` / `lake`
3. Run tests:
   - Python: `pytest`
   - Node: `pnpm test`
   - Lean: `lake build`

## Pull Request Checklist

Before opening a PR, confirm:

- [ ] Commits are signed / verified
- [ ] Tests pass locally
- [ ] Documentation is updated if behavior changed
- [ ] `STATUS.md` remains accurate
- [ ] `SECURITY.md` and `LICENSE` are present

## Code of Conduct

This project follows the [Contributor Covenant v2.1](./CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions are licensed under [Apache-2.0](./LICENSE).
