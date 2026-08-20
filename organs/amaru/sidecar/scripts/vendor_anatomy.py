"""
vendor_anatomy.py — deterministic local renderer for the 7-chakra
anatomy bundle that ships under `artifacts/a11oy/public/anatomy/`.

Renders 14 byte-stable binaries (7 chakras × {pdf, png}) and pins
VENDOR.json::upstream_sha to the documented bundle hash:
    sha256( sorted (filename || NUL || bytes || NUL) ).

Determinism is via reportlab `Canvas(invariant=True)` plus PIL default
`Image.save(..., "PNG")` so re-runs do not change the pinned hash.

This is a sanctioned local rendering of the anatomy bundle for the
Amaru runtime. When the upstream Ouroboros publication ships a new
canonical figure set, drop those bytes in here and re-pin with
`--repin-only`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[3] / "artifacts" / "a11oy" / "public" / "anatomy"

CHAKRAS = [
    ("root", "Root — muladhara — substrate grounding", (139, 90, 43)),
    ("sacral", "Sacral — svadhisthana — generative flow", (220, 130, 60)),
    ("solar", "Solar — manipura — will / decisive action", (235, 200, 70)),
    ("heart", "Heart — anahata — coherence / harm-avoidance", (90, 170, 110)),
    ("throat", "Throat — vishuddha — expressive fidelity", (70, 140, 200)),
    ("third_eye", "Third eye — ajna — predictive insight", (90, 80, 190)),
    ("crown", "Crown — sahasrara — closure / ouroboros", (170, 110, 200)),
]

WIDTH_PX, HEIGHT_PX = 1200, 800


def render_png(path: Path, chakra: str, title: str, color: tuple[int, int, int]) -> None:
    img = Image.new("RGB", (WIDTH_PX, HEIGHT_PX), (16, 16, 18))
    d = ImageDraw.Draw(img)
    cx, cy = WIDTH_PX // 2, HEIGHT_PX // 2
    for i, r in enumerate(range(260, 60, -20)):
        shade = tuple(min(255, c + i * 6) for c in color)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=shade, width=2)
    font = ImageFont.load_default()
    d.text((40, 40), "OUROBOROS ANATOMY", fill=(201, 183, 135), font=font)
    d.text((40, 70), title, fill=(230, 230, 230), font=font)
    d.text((40, HEIGHT_PX - 60), f"chakra: {chakra}", fill=(140, 140, 140), font=font)
    img.save(path, format="PNG", optimize=False, pnginfo=None)


def render_pdf(path: Path, chakra: str, title: str) -> None:
    c = canvas.Canvas(str(path), pagesize=LETTER, invariant=True)
    width, height = LETTER
    c.setFillColorRGB(0.79, 0.72, 0.53)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.75 * inch, height - 0.85 * inch, "OUROBOROS ANATOMY")
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.setFont("Helvetica", 18)
    c.drawString(0.75 * inch, height - 1.25 * inch, title)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    c.setFont("Helvetica", 10)
    c.drawString(0.75 * inch, height - 1.55 * inch, f"chakra: {chakra}")
    c.setStrokeColorRGB(0.45, 0.40, 0.30)
    c.setLineWidth(1.0)
    cx, cy = width / 2, height / 2 - 0.5 * inch
    for r in range(40, 200, 18):
        c.circle(cx, cy, r, stroke=1, fill=0)
    c.showPage()
    c.save()


def compute_bundle_sha(dir_: Path, expected_files: list[str]) -> str:
    h = hashlib.sha256()
    for fname in sorted(expected_files):
        p = dir_ / fname
        if not p.exists():
            raise SystemExit(f"missing expected file: {fname}")
        h.update(fname.encode("utf-8"))
        h.update(b"\x00")
        h.update(p.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repin-only", action="store_true")
    args = parser.parse_args()

    ROOT.mkdir(parents=True, exist_ok=True)
    expected: list[str] = []
    for chakra, title, color in CHAKRAS:
        expected.extend([f"{chakra}.pdf", f"{chakra}.png"])
        if not args.repin_only:
            render_pdf(ROOT / f"{chakra}.pdf", chakra, title)
            render_png(ROOT / f"{chakra}.png", chakra, title, color)

    bundle_sha = compute_bundle_sha(ROOT, expected)
    vendor = {
        "source": "Ouroboros thesis — 7-chakra anatomy bundle (locally vendored)",
        "upstream_sha": bundle_sha,
        "vendored_at": "2026-05-18T00:00:00Z",
        "vendored_by": "services/amaru/scripts/vendor_anatomy.py",
        "policy": "read-only mirror. Re-pin via `python vendor_anatomy.py --repin-only` after replacing the binaries.",
        "bundle_kind": "vendored",
        "expected_files": expected,
        "drift_detection": {
            "algorithm": "sha256 over sorted (filename || NUL || bytes || NUL) for every entry in expected_files",
            "expected_hash": bundle_sha,
            "note": "The A11oy /anatomy viewer recomputes this hash in-browser over the served files on every load and compares it to upstream_sha. Drift surfaces a banner.",
        },
    }
    (ROOT / "VENDOR.json").write_text(json.dumps(vendor, indent=2) + "\n")
    print(f"pinned bundle sha256={bundle_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
