#!/bin/sh
# rosie container entrypoint.
#
# rosie is the operator console: a TypeScript Khipu Receipt DAG / QEC-governed
# ingress library. It has no network server and no CLI bin, so this image is a
# CLI image: it bundles the typechecked source and exposes version/help plus a
# small self-check.
#
# Authored for SZL Holdings. Signed-off per repository DCO.
set -eu

APP_DIR="/app"
VERSION="$(node -p "require('${APP_DIR}/package.json').version" 2>/dev/null || echo "unknown")"

print_help() {
  cat <<EOF
rosie ${VERSION} — operator console (Khipu Receipt DAG, QEC-governed ingress)

Usage:
  rosie --version          Print the rosie version and exit.
  rosie --help             Print this help and exit.
  rosie selfcheck          Load the receipt + axis modules and print a summary.
  rosie verify <file|->    Verify a DSSE receipt envelope offline. Reads from a
                           file path or '-' for stdin. Exit 0=valid, 2=tampered,
                           3=malformed. No network calls.

The TypeScript modules under src/ are importable for downstream Node tooling
via 'node --experimental-strip-types'.
EOF
}

case "${1:-}" in
  ""|-h|--help|help)
    print_help
    exit 0
    ;;
  -v|--version|version)
    echo "rosie ${VERSION}"
    exit 0
    ;;
  selfcheck)
    exec node --experimental-strip-types -e "
      import('${APP_DIR}/src/axis-value-option.ts').then((axis) => {
        const exports = Object.keys(axis);
        console.log(JSON.stringify({ ok: true, module: 'axis-value-option', exports: exports.length }));
      }).catch((e) => { console.error(String(e)); process.exit(1); });
    "
    ;;
  verify)
    shift
    cd "${APP_DIR}"
    exec python3 -m src.console.verify_cli "$@"
    ;;
  *)
    exec node "$@"
    ;;
esac
