# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Emit actual generator HTML for local browser fixtures; never call a publisher."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_hf_publish_vertical_flagships_v4 import load_overlay


def denied(*args, **kwargs):
    raise RuntimeError('network is forbidden while materializing native fixtures')


def main():
    output = Path(sys.argv[1]); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    socket.create_connection = denied
    socket.socket.connect = denied
    module = load_overlay()
    pages = {r['slug']: module.html(r) for r in module.FLAGSHIPS if r['slug'] in module._native_module.SLUGS}
    pages['terra-landing'], forge = module.load_terra_native_landing()
    receipt = {'schema':'szl.vertical-native-fixtures/v1', 'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'scope':'unsigned generated HTML fixtures; no publisher or provider operation', 'files':{}, 'terra':forge}
    for name, page in pages.items():
        raw = page.encode(); (output/(name+'.html')).write_bytes(raw)
        receipt['files'][name+'.html'] = hashlib.sha256(raw).hexdigest()
    (output/'source.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__ == '__main__': main()
