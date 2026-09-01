#!/usr/bin/env python3
# Apply the bounded A11oy production-convergence source repair.
#
# This helper is installed only on the repair branch and deleted by the workflow
# after the reviewed diff passes its focused contracts.
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def patch_rollout() -> None:
    path = ROOT / "scripts" / "rollout_frontend_flow_shell.py"
    replace_once(
        path,
        'EXCLUDE_PARTS = {"node_modules", "vendor", "archive", "archives", "fixtures", ".git"}\n\n\ndef candidates() -> list[Path]:',
        '''EXCLUDE_PARTS = {"node_modules", "vendor", "archive", "archives", "fixtures", ".git"}
SOURCE_MANAGED_PATHS = {"pages/integrations.html"}
SOURCE_BOUNDARY_MARKERS = ("DO NOT EDIT HERE.", "VENDORED FROM ")


def source_managed(path: Path) -> bool:
    # Another source contract owns these HTML bytes.
    rel = path.relative_to(ROOT).as_posix()
    if rel in SOURCE_MANAGED_PATHS:
        return True
    try:
        head = path.read_text(encoding="utf-8")[:4096]
    except (OSError, UnicodeError):
        return False
    return any(marker in head for marker in SOURCE_BOUNDARY_MARKERS)


def candidates() -> list[Path]:''',
        "rollout source-boundary constants",
    )
    replace_once(
        path,
        '''        if path.is_file():
            found.add(path)''',
        '''        if path.is_file() and not source_managed(path):
            found.add(path)''',
        "rollout exact candidate boundary",
    )
    replace_once(
        path,
        '''            if path.is_file() and not (set(path.relative_to(ROOT).parts) & EXCLUDE_PARTS):
                found.add(path)''',
        '''            if (
                path.is_file()
                and not (set(path.relative_to(ROOT).parts) & EXCLUDE_PARTS)
                and not source_managed(path)
            ):
                found.add(path)''',
        "rollout glob candidate boundary",
    )
    replace_once(
        path,
        '''def update_state(changed: list[str], examined: int) -> None:
    payload = json.loads(STATE.read_text(encoding="utf-8"))
    payload["state"] = "ROLLED_OUT"
    payload["examined_documents"] = examined
    payload["injected_documents"] = changed''',
        '''def update_state(bound: list[str], examined: int) -> None:
    payload = json.loads(STATE.read_text(encoding="utf-8"))
    payload["state"] = "ROLLED_OUT"
    payload["examined_documents"] = examined
    payload["injected_documents"] = bound''',
        "rollout complete state bookkeeping",
    )
    replace_once(
        path,
        '''    rows = []
    changed: list[str] = []
    for path in candidates():''',
        '''    rows = []
    changed: list[str] = []
    bound: list[str] = []
    for path in candidates():''',
        "rollout bound list",
    )
    replace_once(
        path,
        '''        if result == "injected":
            changed.append(rel)

    if not rows:''',
        '''        if result == "injected":
            changed.append(rel)
        if result in {"injected", "present"}:
            bound.append(rel)

    if not rows:''',
        "rollout bound collection",
    )
    replace_once(
        path,
        '''    if not args.check:
        update_state(changed, len(rows))''',
        '''    if not args.check:
        update_state(bound, len(rows))''',
        "rollout state call",
    )
    replace_once(
        path,
        '''        "changed": len(changed),
        "rows": rows,''',
        '''        "changed": len(changed),
        "bound": len(bound),
        "rows": rows,''',
        "rollout report bound count",
    )


def patch_mobile_geometry() -> None:
    replace_once(
        ROOT / "console" / "assets" / "szl-flow.css",
        ".szl-flow-toggle { display: none; }",
        '''.szl-flow-toggle {
  display: none;
  min-width: 48px;
  min-height: 48px;
  border-radius: 6px;
}''',
        "Flow Shell mobile menu hit geometry",
    )

    old_cta = ".cta-row .btn{width:100%;white-space:normal;text-align:center}"
    new_cta = (
        ".cta-row .btn{width:100%;min-height:52px;border-radius:6px;"
        "white-space:normal;text-align:center}"
    )
    replace_once(
        ROOT / "a11oy_landing.html",
        old_cta,
        new_cta,
        "front-door mobile CTA geometry",
    )

    repair = ROOT / "scripts" / "repair_a11oy_frontdoor.py"
    repair_text = repair.read_text(encoding="utf-8")
    marker = "MOBILE_FINAL_BLOCK ="
    before, separator, after = repair_text.partition(marker)
    if not separator:
        raise SystemExit("front-door repair: MOBILE_FINAL_BLOCK anchor missing")
    if after.count(old_cta) < 1:
        raise SystemExit("front-door repair: mobile CTA anchor missing after final block")
    after = after.replace(old_cta, new_cta, 1)
    repair.write_text(before + separator + after, encoding="utf-8", newline="\n")


def patch_edge_workflow() -> None:
    path = ROOT / ".github" / "workflows" / "repair-cloudflare-product-edge.yml"
    replace_once(
        path,
        '''    paths:
      - ".github/workflows/repair-cloudflare-product-edge.yml"''',
        '''    paths:
      - ".github/workflows/repair-cloudflare-product-edge.yml"
      - "cloudflare/**"
      - "scripts/repair_cloudflare_product_edge.py"
      - "tests/test_cloudflare_product_edge.py"
      - "szl_connectors_serve.py"
      - "a11oy_landing.html"
      - "console/assets/szl-flow.css"
      - "scripts/rollout_frontend_flow_shell.py"
      - "pages/integrations.html"
      - "spaces/sda/index.html"''',
        "Cloudflare production-surface triggers",
    )
    replace_once(
        path,
        '''env:
  EDGE_REPORT: /tmp/cloudflare-product-edge.json''',
        '''concurrency:
  group: cloudflare-product-root
  cancel-in-progress: false

env:
  EDGE_REPORT: /tmp/cloudflare-product-edge.json''',
        "Cloudflare repair serialization",
    )


def patch_ghcr_workflow() -> None:
    path = ROOT / ".github" / "workflows" / "ghcr-build-push.yml"
    replace_once(
        path,
        "      attestations: write\n",
        "      attestations: write\n      artifact-metadata: write\n",
        "GHCR artifact metadata permission",
    )
    replace_once(
        path,
        '''      - name: cosign sign
        env:
          COSIGN_EXPERIMENTAL: "1"
        run: |
          cosign sign --yes ghcr.io/szl-holdings/${{ github.event.repository.name }}:uds-v0.3.0
          cosign sign --yes ghcr.io/szl-holdings/${{ github.event.repository.name }}:latest''',
        '''      - name: cosign sign
        env:
          COSIGN_EXPERIMENTAL: "1"
          IMG: ghcr.io/szl-holdings/${{ github.event.repository.name }}
          DIGEST: ${{ steps.build-push.outputs.digest }}
        run: |
          set -euo pipefail
          for attempt in 1 2 3; do
            if cosign sign --yes "${IMG}@${DIGEST}"; then
              echo "Signed immutable image ${IMG}@${DIGEST}."
              exit 0
            fi
            if [ "${attempt}" -eq 3 ]; then
              echo "::error::Sigstore signing failed after ${attempt} bounded attempts."
              exit 1
            fi
            sleep $((attempt * 10))
          done''',
        "GHCR immutable digest signing",
    )


def write_source_boundary_test() -> None:
    path = ROOT / "tests" / "test_frontend_source_boundaries.py"
    path.write_text(
        '''#!/usr/bin/env python3
# Regression contract for Flow Shell source ownership and mobile hit geometry.
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLLOUT_PATH = ROOT / "scripts" / "rollout_frontend_flow_shell.py"
STYLE_MARKER = 'data-szl-flow-asset="style"'
SCRIPT_MARKER = 'data-szl-flow-asset="script"'


def load_rollout():
    spec = importlib.util.spec_from_file_location("rollout_frontend_flow_shell", ROLLOUT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load rollout module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrontendSourceBoundaryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rollout = load_rollout()

    def test_shared_and_vendored_html_are_never_source_mutated(self) -> None:
        integrations = ROOT / "pages" / "integrations.html"
        sda = ROOT / "spaces" / "sda" / "index.html"
        self.assertTrue(self.rollout.source_managed(integrations))
        self.assertTrue(self.rollout.source_managed(sda))

        candidates = {path.relative_to(ROOT).as_posix() for path in self.rollout.candidates()}
        self.assertNotIn("pages/integrations.html", candidates)
        self.assertNotIn("spaces/sda/index.html", candidates)

        for path in (integrations, sda):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(STYLE_MARKER, text, path.as_posix())
            self.assertNotIn(SCRIPT_MARKER, text, path.as_posix())

    def test_rollout_state_contains_only_eligible_bound_documents(self) -> None:
        state = json.loads(
            (ROOT / "docs" / "frontend-flow-shell-state.json").read_text(encoding="utf-8")
        )
        bound = set(state["injected_documents"])
        eligible = {path.relative_to(ROOT).as_posix() for path in self.rollout.candidates()}
        self.assertEqual(bound, eligible)
        self.assertEqual(state["examined_documents"], len(eligible))

    def test_mobile_controls_have_safe_rounded_hit_geometry(self) -> None:
        css = (ROOT / "console" / "assets" / "szl-flow.css").read_text(encoding="utf-8")
        toggle = re.search(r"\.szl-flow-toggle\s*\{(?P<body>[^}]*)\}", css, re.S)
        self.assertIsNotNone(toggle)
        body = toggle.group("body")
        self.assertIn("min-width: 48px", body)
        self.assertIn("min-height: 48px", body)
        self.assertIn("border-radius: 6px", body)

        landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        self.assertIn(
            ".cta-row .btn{width:100%;min-height:52px;border-radius:6px;"
            "white-space:normal;text-align:center}",
            landing,
        )


if __name__ == "__main__":
    unittest.main()
''',
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    patch_rollout()
    patch_mobile_geometry()
    patch_edge_workflow()
    patch_ghcr_workflow()
    write_source_boundary_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
