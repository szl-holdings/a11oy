#!/bin/sh
# a11oy container entrypoint.
#
# a11oy is a TypeScript policy/receipt substrate (library + CLI), not a
# long-running network service. This image is therefore a CLI image: it
# bundles the doctrine packages (built to dist/) and the receipt-substrate
# CLI, and dispatches to them.
#
# Authored for SZL Holdings. Signed-off per repository DCO.
set -eu

APP_DIR="/app"
VERSION="$(node -p "require('${APP_DIR}/package.json').version" 2>/dev/null || echo "unknown")"

print_help() {
  cat <<EOF
a11oy ${VERSION} — governed policy / receipt substrate (CLI image)

Usage:
  a11oy --version            Print the a11oy version and exit.
  a11oy --help               Print this help and exit.
  a11oy receipt [args...]    Run the receipt-substrate CLI. It chains an
                             MCP-style tool-envelope receipt to a JSONL ledger.
                             Required args:
                               --out <file> --actor <id> --tool <name> \\
                               --payload-json <json>
                             Optional:
                               --protocol <mcp> --quorum <1-of-1> \\
                               --nodes <a,b> --lambda-axes <Λ7,...>

Examples:
  a11oy receipt --out /tmp/receipts.jsonl --actor did:example:operator \\
    --tool receipted_retrieval --payload-json '{"query":"status","limit":3}'

The doctrine packages (@a11oy/core, @a11oy/connection) are built to dist/ in
this image and importable for downstream Node tooling.
EOF
}

case "${1:-}" in
  ""|-h|--help|help)
    print_help
    exit 0
    ;;
  -v|--version|version)
    echo "a11oy ${VERSION}"
    exit 0
    ;;
  receipt)
    shift
    exec node --experimental-strip-types \
      "${APP_DIR}/packages/receipt-substrate/src/cli.ts" "$@"
    ;;
  *)
    # Pass through to node for any other invocation (e.g. running a script).
    exec node "$@"
    ;;
esac
