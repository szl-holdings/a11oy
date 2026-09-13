# SPDX-License-Identifier: Apache-2.0
"""Build/check the product's derived view of the existing public HF manifest.

No network, credentials, weight downloads or training. The inventory remains
owned by scripts/audit_huggingface_ecosystem.py. This copies only presentation
fields into the already-copied routers/data directory of the product image.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from routers.model_pretraining import MANIFEST, SOURCE_MANIFEST, MAX_BYTES, build_projection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    args = parser.parse_args()
    with SOURCE_MANIFEST.open('rb') as stream:
        expected = build_projection(stream.read(MAX_BYTES + 1))
    if args.check:
        try:
            with MANIFEST.open('rb') as stream:
                actual = stream.read(MAX_BYTES + 1)
        except OSError:
            print('MODEL_PROJECTION_MISSING')
            return 1
        if actual != expected:
            print('MODEL_PROJECTION_DRIFT')
            return 1
        print('MODEL_PROJECTION_MATCHES_SOURCE_NOT_MODEL_QUALIFICATION')
        return 0
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_bytes(expected)
    print('MODEL_PROJECTION_WRITTEN_NO_PROVIDER_MUTATION')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
