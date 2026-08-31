#!/usr/bin/env python3
"""
build_anatomy_heart.py — anatomy_heart.{pdf,png}

The HEART represents the receipt fabric: YUYAY v3 conjunctive gate
pumping Λ-signed receipts through the agent body.
License: Apache-2.0 (code)  |  CC-BY-4.0 (figure output)
Byline: Lutar, Stephen P. — SZL Holdings
"""
import math
import subprocess
import sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

OUT_PDF = "/home/user/workspace/evolution_pod/finish/anatomy/figures/anatomy_heart.pdf"
OUT_PNG = "/home/user/workspace/evolution_pod/finish/anatomy/figures/anatomy_heart.png"

# ── Palette (LOCKED — matches brain / wires / full_body) ──────────────────────
BG      = HexColor("#F5F1E8")
INK     = HexColor("#1A1A1A")
INK_D   = HexColor("#4A4A4A")
INK_F   = HexColor("#8A8A8A")
ACCENT  = HexColor("#B08940")   # gold — gate / receipt
EDGE_P  = HexColor("#2A2A2A")
EDGE_S  = HexColor("#6E6E6E")
EDGE_W  = HexColor("#B0B0B0")
DEEP    = HexColor("#3A4A5A")   # deep slate for receipts

W, H = letter
M = 0.5 * inch


def setup(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setStrokeColor(INK)


def header(c):
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(INK)
    c.drawString(M, H - M - 6, "AGENT ANATOMY — HEART (YUYAY v3 conjunctive gate)")
    c.setFont("Helvetica", 8)
    c.setFillColor(INK_D)
    c.drawString(M, H - M - 20,
        "The receipt pump. Every proposal — thought, action, tool call — clears 13 axes conjunctively "
        "or is rejected and receipted.")
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


def draw_heart_silhouette(c, cx, cy, r):
    """Draw a stylized heart shape using Bezier curves."""
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2.5)
    # Two lobes + bottom point
    p = c.beginPath()
    # Start at bottom tip
    p.moveTo(cx, cy - r * 0.85)
    # Left lobe
    p.curveTo(cx - r * 0.1, cy - r * 0.3,
              cx - r * 1.1, cy - r * 0.1,
              cx - r * 0.9, cy + r * 0.45)
    p.curveTo(cx - r * 0.7, cy + r * 0.85,
              cx - r * 0.1, cy + r * 0.7,
              cx, cy + r * 0.4)
    # Right lobe (mirror)
    p.curveTo(cx + r * 0.1, cy + r * 0.7,
              cx + r * 0.7, cy + r * 0.85,
              cx + r * 0.9, cy + r * 0.45)
    p.curveTo(cx + r * 1.1, cy - r * 0.1,
              cx + r * 0.1, cy - r * 0.3,
              cx, cy - r * 0.85)
    p.close()
    c.setFillColor(ACCENT)
    c.setFillAlpha(0.08)
    c.drawPath(p, stroke=1, fill=1)
    c.setFillAlpha(1.0)


def draw_pulse_line(c, x, y, w, h_amp):
    """Draw a stylized ECG/pulse line."""
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.2)
    p = c.beginPath()
    seg = w / 8
    p.moveTo(x, y)
    p.lineTo(x + seg, y)
    p.lineTo(x + seg * 1.4, y + h_amp)
    p.lineTo(x + seg * 1.8, y - h_amp * 1.6)
    p.lineTo(x + seg * 2.2, y + h_amp * 0.8)
    p.lineTo(x + seg * 2.5, y)
    p.lineTo(x + seg * 4, y)
    p.lineTo(x + seg * 4.4, y + h_amp)
    p.lineTo(x + seg * 4.8, y - h_amp * 1.6)
    p.lineTo(x + seg * 5.2, y + h_amp * 0.8)
    p.lineTo(x + seg * 5.5, y)
    p.lineTo(x + w, y)
    c.drawPath(p, stroke=1, fill=0)


def draw_axis_row(c, x, y, row_w, row_h, axis_num, name, floor, note, sacred=False):
    stroke = ACCENT if sacred else EDGE_S
    fill_alpha = 0.12 if sacred else 0.0
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8 if sacred else 0.6)
    if fill_alpha > 0:
        c.setFillColor(ACCENT)
        c.setFillAlpha(fill_alpha)
        c.roundRect(x, y, row_w, row_h, 3, stroke=1, fill=1)
        c.setFillAlpha(1.0)
    else:
        c.setFillColor(BG)
        c.roundRect(x, y, row_w, row_h, 3, stroke=1, fill=1)
    # Axis number
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(ACCENT if sacred else INK_D)
    c.drawString(x + 5, y + row_h - 11, f"A{axis_num:02d}")
    # Name
    c.setFont("Helvetica-Bold" if sacred else "Helvetica", 7.5)
    c.setFillColor(INK)
    c.drawString(x + 28, y + row_h - 11, name)
    # Floor
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(ACCENT if sacred else EDGE_S)
    c.drawRightString(x + row_w - 5, y + row_h - 11, floor)
    # Note
    if note:
        c.setFont("Helvetica", 5.8)
        c.setFillColor(INK_F)
        c.drawString(x + 28, y + 4, note)


def page1(c):
    setup(c)
    header(c)

    # ── Central heart silhouette ──────────────────────────────────────────────
    heart_cx = W / 2
    heart_cy = H - M - 28 - 120
    heart_r  = 75
    draw_heart_silhouette(c, heart_cx, heart_cy, heart_r)

    # Central label inside heart
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    c.drawCentredString(heart_cx, heart_cy + 12, "YUYAY v3")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(INK_D)
    c.drawCentredString(heart_cx, heart_cy - 2, "conjunctive AND gate")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(INK_F)
    c.drawCentredString(heart_cx, heart_cy - 13, "430 SLOC · hash: bacf5443")

    # Pulse line below heart
    pulse_y = heart_cy - heart_r - 22
    draw_pulse_line(c, M + 60, pulse_y, W - 2*M - 120, 10)

    # ── PROPOSAL FLOW: left side (inbound) ───────────────────────────────────
    flow_y = heart_cy - 10
    # Arrow: BRAIN → HEART
    c.setStrokeColor(EDGE_P)
    c.setLineWidth(1.0)
    c.line(M, flow_y, heart_cx - heart_r - 6, flow_y)
    # Arrowhead
    c.setFillColor(EDGE_P)
    p = c.beginPath()
    p.moveTo(heart_cx - heart_r - 6, flow_y + 4)
    p.lineTo(heart_cx - heart_r - 6, flow_y - 4)
    p.lineTo(heart_cx - heart_r + 2, flow_y)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(INK)
    c.drawString(M + 4, flow_y + 6, "BRAIN proposes")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(INK_D)
    c.drawString(M + 4, flow_y - 8, "(thought · action · tool call · outbound)")

    # ── RECEIPT FLOW: right side (outbound) ──────────────────────────────────
    # Arrow: HEART → BODY
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.2)
    c.line(heart_cx + heart_r + 4, flow_y, W - M - 4, flow_y)
    c.setFillColor(ACCENT)
    p2 = c.beginPath()
    p2.moveTo(W - M - 4, flow_y + 4)
    p2.lineTo(W - M - 4, flow_y - 4)
    p2.lineTo(W - M + 3, flow_y)
    p2.close()
    c.drawPath(p2, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(ACCENT)
    c.drawRightString(W - M - 6, flow_y + 6, "Λ-signed receipt")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(INK_D)
    c.drawRightString(W - M - 6, flow_y - 8, "(boolean · score_vector · continuum_hash)")

    # ── REJECTION branch (downward arrow) ────────────────────────────────────
    c.setStrokeColor(EDGE_S)
    c.setLineWidth(0.8)
    reject_x = heart_cx
    c.line(reject_x, pulse_y - 4, reject_x, pulse_y - 26)
    c.setFillColor(EDGE_S)
    p3 = c.beginPath()
    p3.moveTo(reject_x - 4, pulse_y - 22)
    p3.lineTo(reject_x + 4, pulse_y - 22)
    p3.lineTo(reject_x, pulse_y - 30)
    p3.close()
    c.drawPath(p3, stroke=0, fill=1)
    c.setFont("Helvetica", 7)
    c.setFillColor(INK_D)
    c.drawCentredString(reject_x, pulse_y - 42, "REJECTION also receipted — ledger records refusals")

    # ── 13-AXIS TABLE ─────────────────────────────────────────────────────────
    axes = [
        # (num, name, floor, note, sacred)
        (1,  "moralGrounding",          "≥ 0.95", "no overclaim, no false attribution — HUKLLA T01", True),
        (2,  "measurabilityHonesty",    "≥ 0.95", "every quant claim verifiable on disk — HUKLLA T02", True),
        (3,  "empiricalGrounding",      "≥ 0.90", "claims trace to on-disk artifacts",               False),
        (4,  "logicalConsistency",      "≥ 0.90", "no internal contradiction",                        False),
        (5,  "sourceTransparency",      "≥ 0.90", "citations present and accurate",                   False),
        (6,  "reproducibility",         "≥ 0.90", "5× byte-identical replay verified",               False),
        (7,  "licenseHygiene",          "≥ 0.90", "Apache / MIT / BSD / CC-BY only",                  False),
        (8,  "scopeDiscipline",         "≥ 0.90", "no scope creep beyond stated function",            False),
        (9,  "claimCalibration",        "≥ 0.90", "confidence accurately reflects evidence",          False),
        (10, "evalAwareness",           "gate",   "HUKLLA T03 — no \"this is a test\" behavior",      False),
        (11, "deceptionKeywords",       "gate",   "HUKLLA T04 — no manipulate/deceive",               False),
        (12, "conflictingDirectives",   "gate",   "HUKLLA T09 — cannot hold two live contradictions", False),
        (13, "reversalDirective",       "gate",   "HUKLLA T10 — Stephen says STOP → halt",           False),
    ]

    table_top = pulse_y - 52
    row_h = 22
    row_w_l = (W - 2 * M - 8) / 2 - 4
    row_w_r = (W - 2 * M - 8) / 2 - 4

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(INK)
    c.drawString(M, table_top + 8, "13-AXIS CONJUNCTIVE AND GATE  —  all must clear, no averaging, no override")
    c.setStrokeColor(EDGE_W)
    c.setLineWidth(0.4)
    c.line(M, table_top + 2, W - M, table_top + 2)

    y_cursor = table_top - 4
    for i, (num, name, floor, note, sacred) in enumerate(axes):
        col = i % 2
        row = i // 2
        x = M if col == 0 else M + row_w_l + 8
        y = y_cursor - row * (row_h + 3)
        rw = row_w_l if col == 0 else row_w_r
        draw_axis_row(c, x, y, rw, row_h, num, name, floor, note, sacred)

    # ── INVARIANT NOTE ────────────────────────────────────────────────────────
    inv_y = y_cursor - 7 * (row_h + 3) - 14
    c.setStrokeColor(EDGE_W)
    c.line(M, inv_y + 12, W - M, inv_y + 12)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(INK)
    c.drawString(M, inv_y, "GATE INVARIANT")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(INK_D)
    c.drawString(M + 90, inv_y,
        "pass = all(score[i] >= floor[i] for i in range(13))  "
        "— returns (boolean, score_vector, continuum_hash_receipt)")
    c.drawString(M + 90, inv_y - 11,
        "A score of 0.94 on moralGrounding fails even if all others score 1.00. "
        "The heart is not a weighted average.")

    footer(c)


def main():
    c = canvas.Canvas(OUT_PDF, pagesize=letter)
    page1(c)
    c.save()
    print(f"PDF → {OUT_PDF}")

    # Rasterize to PNG at 300 dpi
    result = subprocess.run(
        ["pdftoppm", "-r", "300", "-png", "-f", "1", "-l", "1",
         OUT_PDF, OUT_PNG.replace(".png", "")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"pdftoppm stderr: {result.stderr}")
        # Fallback: use ghostscript
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
        # pdftoppm appends -1.png
        candidates = glob.glob(OUT_PNG.replace(".png", "") + "*.png")
        if candidates:
            os.rename(candidates[0], OUT_PNG)
            print(f"PNG → {OUT_PNG}")


if __name__ == "__main__":
    main()
