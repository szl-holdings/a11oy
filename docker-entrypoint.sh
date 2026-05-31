#!/bin/sh
# a11oy container entrypoint.
#
# a11oy is a TypeScript policy/receipt substrate. This image bundles the
# doctrine packages (built to dist/) and the receipt-substrate CLI, and can run
# in two modes:
#   - CLI mode:   a11oy <subcommand> [args...]  (selftest, receipt, ...)
#   - serve mode: a11oy serve --port 8080        (HTTP server with /healthz,
#                 /readyz, /v1/ledger, /v1/verify, /v1/policy/evaluate)
# The serve mode is what the Kubernetes liveness/readiness probes target.
#
# Usage:
#   docker run --rm a11oy:dev --help
#   docker run --rm a11oy:dev selftest
#   docker run -p 8080:8080 a11oy:dev serve
#
# Authored for SZL Holdings. Signed-off per repository DCO.
set -eu

APP_DIR="${A11OY_APP_DIR:-/app}"
A11OY_PORT="${A11OY_PORT:-8080}"
VERSION="$(node -p "require('${APP_DIR}/package.json').version" 2>/dev/null || echo "unknown")"

print_help() {
  cat <<EOF
a11oy ${VERSION} — governed policy / receipt substrate

Usage:
  a11oy --version            Print the a11oy version and exit.
  a11oy --help               Print this help and exit.
  a11oy selftest             Run the in-process boot self-test. Emits, reads
                             back, and verifies a receipt chain in a temp file
                             (no network). Exits non-zero if the bundled
                             receipt substrate is not functional in this image.
  a11oy serve                Start the HTTP API server on port ${A11OY_PORT}.
                             Endpoints: GET /healthz  GET /readyz
                             Override port: -e A11OY_PORT=<n>
  a11oy receipt [args...]    Run the receipt-substrate CLI. It chains an
                             MCP-style tool-envelope receipt to a JSONL ledger.
                             Required args:
                               --out <file> --actor <id> --tool <name> \
                               --payload-json <json>
                             Optional:
                               --protocol <mcp> --quorum <1-of-1> \
                               --nodes <a,b> --lambda-axes <Λ7,...>
  a11oy serve [args...]      Boot the HTTP server. Exposes:
                               GET  /healthz   GET  /readyz
                               GET  /v1/ledger?limit=N   GET /v1/ledger/{hash}
                               POST /v1/verify   POST /v1/policy/evaluate
                             Optional:
                               --port <8080> --host <0.0.0.0> --ledger <path>
                             Env: A11OY_PORT, A11OY_PROOF_LEDGER_PATH,
                               A11OY_GIT_SHA

Examples:
  a11oy receipt --out /tmp/receipts.jsonl --actor did:example:operator \
    --tool receipted_retrieval --payload-json '{"query":"status","limit":3}'
  docker run -p 8080:8080 ghcr.io/szl-holdings/a11oy:latest serve

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
  selftest)
    exec node --experimental-strip-types \
      "${APP_DIR}/packages/receipt-substrate/src/selftest.ts"
    ;;
  serve)
    # Delegate to the serve subcommand.  The server module is provided by the
    # serve-BE dev (packages/receipt-substrate/src/server.ts).  If it is not
    # yet present (pre-merge), the container will exit with a clear error
    # rather than silently hang.
    SERVE_SCRIPT="${APP_DIR}/packages/receipt-substrate/src/server.ts"
    if [ ! -f "${SERVE_SCRIPT}" ]; then
      echo "ERROR: serve subcommand not yet available (${SERVE_SCRIPT} missing)." >&2
      echo "The serve-BE PR has not landed yet. See MISSION.md." >&2
      exit 1
    fi
    exec node --experimental-strip-types "${SERVE_SCRIPT}" --port "${A11OY_PORT}"
    ;;
  receipt)
    shift
    exec node --experimental-strip-types \
      "${APP_DIR}/packages/receipt-substrate/src/cli.ts" "$@"
    ;;
  serve)
    shift
    exec node --experimental-strip-types \
      "${APP_DIR}/packages/receipt-substrate/src/serve.ts" "$@"
    ;;
  *)
    # Pass through to node for any other invocation (e.g. running a script).
    exec node "$@"
    ;;
esac
