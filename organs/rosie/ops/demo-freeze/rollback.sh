#!/usr/bin/env bash
# rollback.sh — reset the rosie HF Space to the frozen demo baseline.
# Author: Yachay <yachay@szlholdings.dev>  ·  Doctrine v11 LOCKED (749/14/163)
# Signed-off-by: Yachay <yachay@szlholdings.dev>  ·  cosign keyid: szlholdings-cosign
#
# WHEN TO RUN: a demo-window hotfix to rosie went wrong and you must restore
#   the exact bytes that were live + verified at the freeze point.
#
# WHAT IT DOES: hard-resets the HF Space git repo to the frozen baseline commit
#   and force-pushes it back to the Space. HF rebuilds from that commit.
#   This is DESTRUCTIVE on the Space's main branch — it is the intended rollback.
#
# REQUIREMENTS:
#   - HF_TOKEN env var with write access to SZLHOLDINGS/rosie
#   - git, plus huggingface_hub installed (pip install huggingface_hub)
#
# Frozen baseline (captured 2026-06-01, tagged demo-freeze-baseline-2026-06-09):
#   HF Space  SZLHOLDINGS/rosie  @  6f2c4d433d8bc8e3acae4765dd019c2dd2af2ffe
#   GitHub    szl-holdings/rosie @  42ae673b6742707a76b13080bf40ae40600194cd
set -euo pipefail

SPACE_ID="SZLHOLDINGS/rosie"
FROZEN_HF_SHA="6f2c4d433d8bc8e3acae4765dd019c2dd2af2ffe"
TMP="$(mktemp -d)"
echo "🔁 Rolling back ${SPACE_ID} to frozen baseline ${FROZEN_HF_SHA}"

if [ -z "${HF_TOKEN:-}" ]; then
  echo "❌ HF_TOKEN not set (need write access to ${SPACE_ID})." >&2
  exit 1
fi

# Pre-flight: confirm the target commit exists on the Space before we touch anything.
REV_URL="https://huggingface.co/api/spaces/${SPACE_ID}/revision/${FROZEN_HF_SHA}"
if ! curl -fsS -H "Authorization: Bearer ${HF_TOKEN}" "${REV_URL}" >/dev/null 2>&1; then
  echo "⚠️  Could not confirm ${FROZEN_HF_SHA} on ${SPACE_ID} via API — proceeding via git clone." >&2
fi

git clone "https://user:${HF_TOKEN}@huggingface.co/spaces/${SPACE_ID}" "${TMP}/space"
cd "${TMP}/space"
git fetch --all --tags
echo "Current head: $(git rev-parse HEAD)"

git reset --hard "${FROZEN_HF_SHA}"
echo "Reset to:     $(git rev-parse HEAD)"

# Force-push the frozen state back to the Space (HF rebuilds on push).
git push --force origin HEAD:main

echo "✅ ${SPACE_ID} rolled back to ${FROZEN_HF_SHA}. HF will rebuild."
echo "   Verify: curl -s https://szlholdings-rosie.hf.space/api/rosie/healthz | head -c 200"
echo "   Then re-run the pre-freeze health check before re-enabling traffic."
