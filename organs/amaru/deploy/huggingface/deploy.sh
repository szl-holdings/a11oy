#!/usr/bin/env bash
# Deploy Amaru to Hugging Face Spaces.
# Requires: HF_TOKEN env var, git, and huggingface_hub installed.
#
# Usage: HF_TOKEN=hf_xxx bash deploy/huggingface/deploy.sh [space-name]
#
# Default space: szl-holdings/amaru
set -euo pipefail

SPACE="${1:-szl-holdings/amaru}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [ -z "${HF_TOKEN:-}" ]; then
  echo "ERROR: HF_TOKEN is required. Set it in your environment."
  exit 1
fi

echo "→ Deploying to Hugging Face Space: $SPACE"

# Create/ensure the space exists
python3 -c "
from huggingface_hub import HfApi
api = HfApi()
try:
    api.create_repo('$SPACE', repo_type='space', space_sdk='docker', exist_ok=True)
    print(f'  Space $SPACE ready')
except Exception as e:
    print(f'  Note: {e}')
"

# Clone or update the space repo
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

git clone "https://huggingface.co/spaces/$SPACE" "$TMPDIR/space" 2>/dev/null || \
  git clone "https://user:${HF_TOKEN}@huggingface.co/spaces/$SPACE" "$TMPDIR/space"

cd "$TMPDIR/space"
git config user.email "deploy@szlholdings.com"
git config user.name "Amaru Deploy"

# Clear and copy deployment files
rm -rf ./*
cp "$REPO_ROOT/deploy/huggingface/README.md" ./README.md
cp "$REPO_ROOT/deploy/huggingface/Dockerfile" ./Dockerfile
cp "$REPO_ROOT/deploy/huggingface/serve.py" ./serve.py

# Copy sidecar (backend)
cp -r "$REPO_ROOT/sidecar" ./sidecar/

# Copy web (frontend)
cp -r "$REPO_ROOT/web" ./web/
rm -rf ./web/node_modules ./web/dist

# Commit and push
git add -A
git commit -m "Deploy Amaru full-stack to HF Spaces" --allow-empty
git push "https://user:${HF_TOKEN}@huggingface.co/spaces/$SPACE" main --force

echo ""
echo "✓ Deployed! Space will build at: https://huggingface.co/spaces/$SPACE"
echo "  App URL: https://${SPACE//\//-}.hf.space"
