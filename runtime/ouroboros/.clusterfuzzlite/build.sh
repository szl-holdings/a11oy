#!/bin/bash -eu
# SPDX-License-Identifier: Apache-2.0
# ClusterFuzzLite build script for szl-holdings/ouroboros
# Installs dependencies and compiles fuzzers for Jazzer.js / @jazzer.js/core

cd "$SRC/ouroboros"

# Install workspace dependencies
pnpm install --frozen-lockfile

# Ensure @jazzer.js/core is available for the fuzzer harness
pnpm add --save-dev @jazzer.js/core || true

# Compile TypeScript so the fuzzer can import built modules
pnpm exec tsc -p tsconfig.json --noEmit false --outDir dist 2>/dev/null || true

# Copy each fuzzer JS file to $OUT with a wrapper that jazzer can execute
for fuzzer in "$SRC/ouroboros/.clusterfuzzlite/fuzzers"/*.js; do
  fuzzer_name=$(basename "$fuzzer" .js)
  cp "$fuzzer" "$OUT/${fuzzer_name}.js"
  # Write a shell-script launcher that jazzer.js will invoke
  cat > "$OUT/${fuzzer_name}" <<EOF
#!/bin/bash
node --experimental-vm-modules \
  "$OUT/${fuzzer_name}.js" \$@
EOF
  chmod +x "$OUT/${fuzzer_name}"
done
