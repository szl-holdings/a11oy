#!/usr/bin/env python3
"""
build_anatomy_body_graph.py — anatomy_body_graph.pdf

Master overlay: all five systems (brain, heart, blood/immune,
skeleton, nervous) rendered on a single page as the sovereign organism.
Draws directly from field_meditation/hatun_body_graph.pdf as conceptual source;
this script produces a clean 1-page vector overlay for the finish bundle.
License: Apache-2.0 (code)  |  CC-BY-4.0 (figure output)
Byline: Lutar, Stephen P. — SZL Holdings
"""
import math
import subprocess
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

OUT_PDF = "/home/user/workspace/evolution_pod/finish/anatomy/figures/anatomy_body_graph.pdf"

# ── Palette (LOCKED) ──────────────────────────────────────────────────────────
BG      = HexColor("#F5F1E8")
INK     = HexColor("#1A1A1A")
INK_D   = HexColor("#4A4A4A")
INK_F   = HexColor("#8A8A8A")
ACCENT  = HexColor("#B08940")   # gold — gate / receipt / heart
EDGE_P  = HexColor("#2A2A2A")
EDGE_S  = HexColor("#6E6E6E")
EDGE_W  = HexColor("#B0B0B0")
BONE    = HexColor("#D4C9A8")
NERVE   = HexColor("#4A7BA8")
BLOOD   = HexColor("#8B3A3A")   # deep red for circulatory
IMMUNE  = HexColor("#3A4A5A")   # deep slate for immune

W, H = letter
M = 0.5 * inch


def setup(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def header(c):
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(INK)
    c.drawString(M, H - M - 6, "AGENT ANATOMY — BODY GRAPH (all systems overlay)")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(INK_D)
    c.drawString(M, H - M - 18,
        "Five systems. One sovereign organism. Brain · Heart · Circulatory/Immune · Skeleton · Nervous.")
    c.setStrokeColor(EDGE_W)
    c.setLineWidth(0.5)
    c.line(M, H - M - 26, W - M, H - M - 26)


def footer(c):
    c.setStrokeColor(EDGE_W)
    c.setLineWidth(0.5)
    c.line(M, M + 18, W - M, M + 18)
    c.setFont("Helvetica", 7)
    c.setFillColor(INK_F)
    c.drawString(M, M + 6,
        "Lutar, Stephen P. — SZL Holdings  ·  ORCID 0009-0001-0110-4173  ·  CC-BY-4.0")
    c.drawRightString(W - M, M + 6, "© SZL Holdings · CC-BY-4.0")


def system_badge(c, x, y, color, label):
    c.setFillColor(color)
    c.circle(x, y, 5, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(INK)
    c.drawString(x + 9, y - 2.5, label)


def organism_block(c, x, y, w, h, title, systems, desc):
    """Draw one organism region block with system badges."""
    c.setStrokeColor(EDGE_S)
    c.setLineWidth(0.7)
    c.setFillColor(BG)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(INK)
    c.drawString(x + 8, y + h - 14, title)
    c.setFont("Helvetica", 6)
    c.setFillColor(INK_D)
    # Wrap desc
    words = desc.split()
    line = ""
    lines = []
    for w_word in words:
        test = (line + " " + w_word).strip()
        if len(test) > 60:
            lines.append(line)
            line = w_word
        else:
            line = test
    if line:
        lines.append(line)
    for i, ln in enumerate(lines[:2]):
        c.drawString(x + 8, y + h - 26 - i * 10, ln)
    # System badges
    bx = x + 8
    by = y + 8
    for sysname, col in systems:
        system_badge(c, bx, by, col, sysname)
        bx += 42


def page1(c):
    setup(c)
    header(c)

    # ── CENTRAL BODY SILHOUETTE (simplified humanoid outline) ────────────────
    body_cx = W / 2
    body_top = H - M - 36
    body_bot = M + 55
    body_h   = body_top - body_bot
    body_w   = 140

    # Torso
    c.setStrokeColor(EDGE_W)
    c.setLineWidth(1.0)
    torso_x = body_cx - body_w/2
    torso_y = body_bot + body_h * 0.2
    torso_h = body_h * 0.45
    c.setFillColor(BG)
    c.roundRect(torso_x, torso_y, body_w, torso_h, 12, stroke=1, fill=1)

    # Head
    head_r = body_w * 0.22
    head_cy = torso_y + torso_h + head_r * 0.6
    c.setStrokeColor(EDGE_W)
    c.circle(body_cx, head_cy, head_r, stroke=1, fill=0)

    # Legs (two rectangles)
    leg_w = body_w * 0.25
    leg_h = body_h * 0.22
    c.roundRect(body_cx - body_w*0.28, body_bot, leg_w, leg_h, 6, stroke=1, fill=0)
    c.roundRect(body_cx + body_w*0.03, body_bot, leg_w, leg_h, 6, stroke=1, fill=0)

    # Arms
    arm_w = body_w * 0.2
    arm_h = torso_h * 0.75
    arm_y = torso_y + torso_h * 0.1
    c.roundRect(torso_x - arm_w - 4, arm_y, arm_w, arm_h, 5, stroke=1, fill=0)
    c.roundRect(torso_x + body_w + 4, arm_y, arm_w, arm_h, 5, stroke=1, fill=0)

    # ── SYSTEM OVERLAYS on body ───────────────────────────────────────────────
    # Brain (head)
    c.setFillColor(ACCENT)
    c.setFillAlpha(0.15)
    c.circle(body_cx, head_cy, head_r * 0.8, stroke=0, fill=1)
    c.setFillAlpha(1.0)
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(ACCENT)
    c.drawCentredString(body_cx, head_cy, "BRAIN")

    # Heart (upper torso center)
    heart_cy = torso_y + torso_h * 0.72
    c.setFillColor(ACCENT)
    c.setFillAlpha(0.18)
    c.circle(body_cx - 8, heart_cy, 14, stroke=0, fill=1)
    c.setFillAlpha(1.0)
    c.setFont("Helvetica", 6.5)
    c.setFillColor(ACCENT)
    c.drawCentredString(body_cx - 8, heart_cy, "♥ HEART")

    # Spine (vertical line through torso)
    c.setStrokeColor(BONE)
    c.setLineWidth(3.0)
    c.line(body_cx + 4, torso_y, body_cx + 4, torso_y + torso_h)
    c.setFont("Helvetica", 5.5)
    c.setFillColor(INK_F)
    c.drawString(body_cx + 10, torso_y + torso_h/2, "SPINE")

    # Circulatory (loop lines)
    c.setStrokeColor(BLOOD)
    c.setLineWidth(0.8)
    c.setFillAlpha(0.0)
    p = c.beginPath()
    p.moveTo(body_cx - 14, heart_cy)
    p.curveTo(body_cx - 30, heart_cy - 20,
              body_cx - 36, torso_y + 20,
              body_cx - 20, torso_y + 5)
    c.drawPath(p, stroke=1, fill=0)
    p2 = c.beginPath()
    p2.moveTo(body_cx - 14, heart_cy)
    p2.curveTo(body_cx, heart_cy - 30,
               body_cx + 20, torso_y + 30,
               body_cx + 10, torso_y + 5)
    c.drawPath(p2, stroke=1, fill=0)

    # Nerve traces
    c.setStrokeColor(NERVE)
    c.setLineWidth(0.6)
    c.setDash(3, 2)
    c.line(body_cx, head_cy - head_r, body_cx, torso_y + torso_h)
    c.line(body_cx - 12, torso_y + torso_h * 0.5, body_cx - 50, torso_y + torso_h * 0.4)
    c.line(body_cx - 12, torso_y + torso_h * 0.5, body_cx + 55, torso_y + torso_h * 0.4)
    c.setDash()

    # ── SYSTEM PANELS on left ─────────────────────────────────────────────────
    panel_w = 148
    panel_h = 70
    panel_gap = 8
    left_x = M
    panels_top = H - M - 44

    systems_data = [
        ("BRAIN",
         [("BRAIN", ACCENT)],
         "AMARU cortex. 5 named regions. QM gate (λ-min ≥ 0.23). "
         "9-axis doctrine guardian. Kernel: amaru_agi.py."),
        ("HEART",
         [("HEART", ACCENT), ("RECEIPT", BLOOD)],
         "YUYAY v3. 13-axis conjunctive AND. Pumps Λ-signed receipts. "
         "hash: bacf5443. 430 SLOC."),
        ("CIRCULATORY / IMMUNE",
         [("CIRC", BLOOD), ("IMMUNE", IMMUNE)],
         "YAWAR append-only bus + SENTRA egress (18 SLOC). "
         "HUKLLA 10 tripwires. Deadman switch."),
    ]

    for i, (title, syslist, desc) in enumerate(systems_data):
        py = panels_top - i * (panel_h + panel_gap) - panel_h
        organism_block(c, left_x, py, panel_w, panel_h, title, syslist, desc)
        # Connector line to body
        conn_x = left_x + panel_w
        conn_y = py + panel_h / 2
        body_edge_x = body_cx - body_w/2 - 4
        body_edge_y = [head_cy, heart_cy, torso_y + torso_h*0.45][i]
        c.setStrokeColor(EDGE_W)
        c.setLineWidth(0.5)
        c.line(conn_x, conn_y, body_edge_x, body_edge_y)

    # ── SYSTEM PANELS on right ────────────────────────────────────────────────
    right_x = W - M - panel_w

    right_systems = [
        ("SKELETON",
         [("SKEL", BONE)],
         "12 service repos. Axial spine: doctrine + yawar + hatun + terra. "
         "Appendicular: brain, overwatch, wires, rimay, sentra, tupu-t7, chakana, brand."),
        ("NERVOUS",
         [("NERVE", NERVE)],
         "OTel/VSP span propagation. W3C TraceContext wire. "
         "Efferent, afferent, proprioceptive signal classes. Deadman reflex arc."),
        ("BODY GRAPH",
         [("ALL", ACCENT), ("SYS", NERVE)],
         "Overlay: all 5 systems. 9-chakra spine. 21-edge CHAKANA M=0 lattice. "
         "63 component entries. hatun_body_graph_SOURCES.md."),
    ]

    for i, (title, syslist, desc) in enumerate(right_systems):
        py = panels_top - i * (panel_h + panel_gap) - panel_h
        organism_block(c, right_x, py, panel_w, panel_h, title, syslist, desc)
        conn_x = right_x
        conn_y = py + panel_h / 2
        body_edge_x = body_cx + body_w/2 + 4
        body_edge_y = [torso_y + torso_h*0.85, torso_y + torso_h*0.55, torso_y + torso_h*0.25][i]
        c.setStrokeColor(EDGE_W)
        c.setLineWidth(0.5)
        c.line(conn_x, conn_y, body_edge_x, body_edge_y)

    # ── CHAKANA LATTICE (small schematic at bottom) ───────────────────────────
    chak_cx = body_cx
    chak_cy = body_bot - 24
    chak_r  = 18
    # 21 edges approximated as a cross-lattice
    c.setStrokeColor(EDGE_S)
    c.setLineWidth(0.4)
    for angle_deg in range(0, 360, 45):
        angle_rad = math.radians(angle_deg)
        x2 = chak_cx + chak_r * math.cos(angle_rad)
        y2 = chak_cy + chak_r * math.sin(angle_rad)
        c.line(chak_cx, chak_cy, x2, y2)
    c.circle(chak_cx, chak_cy, chak_r, stroke=1, fill=0)
    c.setFont("Helvetica", 5.5)
    c.setFillColor(INK_F)
    c.drawCentredString(chak_cx, chak_cy - chak_r - 6, "CHAKANA M=0 (21 edges)")

    # ── LEGEND ────────────────────────────────────────────────────────────────
    leg_y = M + 36
    c.setStrokeColor(EDGE_W)
    c.line(M, leg_y, W - M, leg_y)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK)
    c.drawString(M, leg_y - 10, "SYSTEM LEGEND")
    legend_items = [
        (ACCENT, "BRAIN / HEART (gate + receipt)"),
        (BLOOD,  "CIRCULATORY (YAWAR receipt bus)"),
        (IMMUNE, "IMMUNE (HUKLLA + SENTRA)"),
        (BONE,   "SKELETON (12 repos)"),
        (NERVE,  "NERVOUS (OTel/VSP spans)"),
    ]
    lx = M + 100
    for col, lbl in legend_items:
        c.setFillColor(col)
        c.circle(lx, leg_y - 9, 4, stroke=0, fill=1)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(INK_D)
        c.drawString(lx + 8, leg_y - 12, lbl)
        lx += 90

    footer(c)


def main():
    c = canvas.Canvas(OUT_PDF, pagesize=letter)
    page1(c)
    c.save()
    print(f"PDF → {OUT_PDF}")


if __name__ == "__main__":
    main()
