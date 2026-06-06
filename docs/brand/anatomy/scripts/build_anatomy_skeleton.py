#!/usr/bin/env python3
"""
build_anatomy_skeleton.py — anatomy_skeleton.{pdf,png}

The SKELETON represents the 12 service repositories as the structural frame
of the SZL runtime. Each bone = one service repo with role, language, SLOC, status.
License: Apache-2.0 (code)  |  CC-BY-4.0 (figure output)
Byline: Lutar, Stephen P. — SZL Holdings
"""
import subprocess
import sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

OUT_PDF = "/home/user/workspace/evolution_pod/finish/anatomy/figures/anatomy_skeleton.pdf"
OUT_PNG = "/home/user/workspace/evolution_pod/finish/anatomy/figures/anatomy_skeleton.png"

# ── Palette (LOCKED) ──────────────────────────────────────────────────────────
BG      = HexColor("#F5F1E8")
INK     = HexColor("#1A1A1A")
INK_D   = HexColor("#4A4A4A")
INK_F   = HexColor("#8A8A8A")
ACCENT  = HexColor("#B08940")
EDGE_P  = HexColor("#2A2A2A")
EDGE_S  = HexColor("#6E6E6E")
EDGE_W  = HexColor("#B0B0B0")
BONE    = HexColor("#D4C9A8")   # warm bone-white for structural elements

W, H = letter
M = 0.5 * inch


def setup(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def header(c):
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(INK)
    c.drawString(M, H - M - 6, "AGENT ANATOMY — SKELETON (12 service repositories)")
    c.setFont("Helvetica", 8)
    c.setFillColor(INK_D)
    c.drawString(M, H - M - 20,
        "The structural frame. 12 repos form the load-bearing skeleton of the SZL runtime. "
        "Remove one and the posture fails.")
    c.setStrokeColor(EDGE_W)
    c.setLineWidth(0.5)
    c.line(M, H - M - 28, W - M, H - M - 28)


def footer(c):
    c.setStrokeColor(EDGE_W)
    c.setLineWidth(0.5)
    c.line(M, M + 18, W - M, M + 18)
    c.setFont("Helvetica", 7)
    c.setFillColor(INK_F)
    c.drawString(M, M + 6,
        "Lutar, Stephen P. — SZL Holdings  ·  ORCID 0009-0001-0110-4173  ·  CC-BY-4.0")
    c.drawRightString(W - M, M + 6, "© SZL Holdings · CC-BY-4.0")


def bone_card(c, x, y, w, h, repo, role, lang, sloc, status, is_axial=False):
    """Draw one service-repo bone card."""
    stroke = ACCENT if is_axial else EDGE_P
    c.setStrokeColor(stroke)
    c.setLineWidth(1.0 if is_axial else 0.7)
    c.setFillColor(BONE if is_axial else BG)
    c.setFillAlpha(0.5 if is_axial else 1.0)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    c.setFillAlpha(1.0)

    # Repo name (top)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(ACCENT if is_axial else INK)
    c.drawString(x + 7, y + h - 13, repo)

    # Role
    c.setFont("Helvetica", 6.8)
    c.setFillColor(INK_D)
    c.drawString(x + 7, y + h - 24, role)

    # Lang · SLOC · status
    c.setFont("Helvetica", 5.8)
    c.setFillColor(INK_F)
    c.drawString(x + 7, y + 7, f"{lang}  ·  {sloc} SLOC  ·  {status}")


def draw_spine(c, cx, y_top, y_bot, n_vertebrae=5):
    """Draw stylized spine column."""
    c.setStrokeColor(EDGE_P)
    c.setLineWidth(1.5)
    c.line(cx, y_top, cx, y_bot)
    seg_h = (y_top - y_bot) / (n_vertebrae + 1)
    for i in range(1, n_vertebrae + 1):
        vy = y_top - i * seg_h
        vw = 22
        vh = seg_h * 0.6
        c.setFillColor(BONE)
        c.setStrokeColor(EDGE_P)
        c.setLineWidth(0.7)
        c.roundRect(cx - vw/2, vy - vh/2, vw, vh, 3, stroke=1, fill=1)


def page1(c):
    setup(c)
    header(c)

    # ── Layout: central spine + left/right bone cards ─────────────────────────
    # Spine runs vertically through the center
    spine_cx = W / 2
    spine_top = H - M - 38
    spine_bot = M + 55

    draw_spine(c, spine_cx, spine_top, spine_bot, n_vertebrae=6)

    # Column label
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK_D)
    c.drawCentredString(spine_cx, spine_top + 10, "AXIAL SPINE")
    c.setFont("Helvetica", 6)
    c.drawCentredString(spine_cx, spine_top + 2, "(receipt chain + doctrine core)")

    # ── 12 service repos ──────────────────────────────────────────────────────
    # AXIAL (spine): 4 core doctrine/infra repos
    # APPENDICULAR (left/right): 8 capability/service repos

    repos = [
        # (repo, role, lang, sloc, status, side, row, is_axial)
        # Axial — placed alongside spine
        ("szl-doctrine",   "9-axis doctrine + HUKLLA gates",    "Python",  "840",  "live",   "ax", 0, True),
        ("szl-yawar",      "append-only receipt bus",            "Python",  "280",  "live",   "ax", 1, True),
        ("szl-hatun",      "sovereign RAID loop orchestrator",   "Python",  "620",  "live",   "ax", 2, True),
        ("szl-terra",      "React 18 BodyGraph + API surface",   "TS/Py",   "1200", "live",   "ax", 3, True),
        # Left appendicular
        ("szl-brain",      "AMARU cortex + QM gating",          "Python",  "490",  "live",   "L",  0, False),
        ("szl-overwatch",  "R0513 threat-scan + replay",        "Python",  "310",  "live",   "L",  1, False),
        ("szl-wires",      "YAWAR-bus + OTel span bridge",      "Python",  "260",  "live",   "L",  2, False),
        ("szl-rimay",      "natural language output filter",     "Python",  "200",  "live",   "L",  3, False),
        # Right appendicular
        ("szl-sentra",     "egress immune inspector 18 SLOC",    "Python",  "180",  "live",   "R",  0, False),
        ("szl-tupu-t7",    "receipt-token tokenisation layer",   "Python",  "340",  "live",   "R",  1, False),
        ("szl-chakana",    "21-edge M=0 spanning lattice",       "Python",  "430",  "live",   "R",  2, False),
        ("szl-brand",      "assets, figures, explainers",        "Md/PDF",  "N/A",  "active", "R",  3, False),
    ]

    card_w = 175
    card_h = 48
    gap    = 10
    # Positioning
    left_x  = M
    right_x = W - M - card_w
    ax_left_x = spine_cx - card_w - 10
    ax_right_x = spine_cx + 10

    ax_rows = [r for r in repos if r[5] == "ax"]
    left_rows = [r for r in repos if r[5] == "L"]
    right_rows = [r for r in repos if r[5] == "R"]

    total_rows = max(len(ax_rows), len(left_rows), len(right_rows))
    usable_h = spine_top - spine_bot - 20
    row_step = usable_h / (total_rows + 0.5)

    def row_y(row_idx):
        return spine_top - 18 - (row_idx + 0.5) * row_step

    # Draw connector lines + cards
    for repo, role, lang, sloc, status, side, row_idx, is_axial in repos:
        cy = row_y(row_idx)
        card_y = cy - card_h / 2

        if side == "ax":
            # Place axial cards flanking the spine alternately
            if row_idx % 2 == 0:
                cx = ax_left_x
                line_x1 = cx + card_w
                line_x2 = spine_cx - 12
            else:
                cx = ax_right_x
                line_x1 = spine_cx + 12
                line_x2 = cx
            # Connector
            c.setStrokeColor(ACCENT)
            c.setLineWidth(0.7)
            c.setDash(3, 2)
            c.line(line_x1 if row_idx % 2 == 0 else spine_cx + 12,
                   cy,
                   cx if row_idx % 2 != 0 else spine_cx - 12,
                   cy)
            c.setDash()
            bone_card(c, cx, card_y, card_w, card_h,
                      repo, role, lang, sloc, status, is_axial=True)
        elif side == "L":
            cx = left_x
            # Connector from card to spine
            c.setStrokeColor(EDGE_W)
            c.setLineWidth(0.5)
            c.line(cx + card_w, cy, spine_cx - 14, cy)
            bone_card(c, cx, card_y, card_w, card_h,
                      repo, role, lang, sloc, status, is_axial=False)
        else:  # R
            cx = right_x
            c.setStrokeColor(EDGE_W)
            c.setLineWidth(0.5)
            c.line(spine_cx + 14, cy, cx, cy)
            bone_card(c, cx, card_y, card_w, card_h,
                      repo, role, lang, sloc, status, is_axial=False)

    # ── Column headers ────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK_D)
    c.drawCentredString(left_x + card_w / 2, spine_top + 6, "APPENDICULAR LEFT")
    c.drawCentredString(right_x + card_w / 2, spine_top + 6, "APPENDICULAR RIGHT")

    # ── LEGEND ────────────────────────────────────────────────────────────────
    leg_y = spine_bot - 10
    c.setStrokeColor(EDGE_W)
    c.line(M, leg_y + 2, W - M, leg_y + 2)
    c.setFont("Helvetica", 6.5)
    c.setFillColor(INK_D)
    c.drawString(M, leg_y - 8,
        "AXIAL (gold border) = doctrine spine: remove and the entire receipt chain collapses.  "
        "APPENDICULAR = capability bones: removable without killing the organism, but posture degrades.")

    footer(c)


def main():
    c = canvas.Canvas(OUT_PDF, pagesize=letter)
    page1(c)
    c.save()
    print(f"PDF → {OUT_PDF}")

    result = subprocess.run(
        ["pdftoppm", "-r", "300", "-png", "-f", "1", "-l", "1",
         OUT_PDF, OUT_PNG.replace(".png", "")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        result2 = subprocess.run(
            ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha",
             "-r300", f"-sOutputFile={OUT_PNG}", OUT_PDF],
            capture_output=True, text=True
        )
        if result2.returncode == 0:
            print(f"PNG → {OUT_PNG} (via gs)")
        else:
            print(f"PNG conversion failed: {result2.stderr}")
    else:
        import glob, os
        candidates = glob.glob(OUT_PNG.replace(".png", "") + "*.png")
        if candidates:
            os.rename(candidates[0], OUT_PNG)
            print(f"PNG → {OUT_PNG}")


if __name__ == "__main__":
    main()
