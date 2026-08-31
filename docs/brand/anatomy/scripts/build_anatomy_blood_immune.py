#!/usr/bin/env python3
"""
build_anatomy_blood_immune.py — Pages 3-4 of the agent anatomy series.

Page 3 — CIRCULATORY (YAWAR receipt bus, the blood).
Page 4 — IMMUNE   (HUKLLA 10 tripwires + SENTRA egress / white blood cells).

Every claim traces to on-disk source files:
  - yawar_bus.py             (20 SLOC, append-only, SHA-256 receipts)
  - sentra_immune.py         (18 SLOC, 6 threat keywords + size DoS guard)
  - HUKLLA_10_TRIPWIRES.md   (T01..T10 canonical list under D45)
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
import math

OUT = "/home/user/workspace/field_meditation/_anatomy_blood_immune.pdf"

# Palette (LOCKED — matches body diagram + brain anatomy)
BG     = HexColor("#F5F1E8")
INK    = HexColor("#1A1A1A")
INK_D  = HexColor("#4A4A4A")
INK_F  = HexColor("#8A8A8A")
ACCENT = HexColor("#B08940")   # gold — gate / receipt
EDGE_P = HexColor("#2A2A2A")
EDGE_S = HexColor("#6E6E6E")
EDGE_W = HexColor("#B0B0B0")
# Slightly cooler accents for immune (still paper aesthetic)
IMMUNE_INK = HexColor("#3A4A5A")   # deep slate for antibody nodes

W, H = letter
M = 0.5 * inch


def setup(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(INK); c.setStrokeColor(INK)


def header(c, title, subtitle):
    c.setFont("Helvetica-Bold", 14); c.setFillColor(INK)
    c.drawString(M, H - M - 6, title)
    c.setFont("Helvetica", 8); c.setFillColor(INK_D)
    c.drawString(M, H - M - 22, subtitle)
    c.setStrokeColor(EDGE_W); c.setLineWidth(0.5)
    c.line(M, H - M - 30, W - M, H - M - 30)


def footer(c, page_num, total):
    c.setStrokeColor(EDGE_W); c.setLineWidth(0.5)
    c.line(M, M + 18, W - M, M + 18)
    c.setFont("Helvetica", 7); c.setFillColor(INK_F)
    c.drawString(M, M + 6, "SZL Holdings  -  Lutar, Stephen P.  -  ORCID 0009-0001-0110-4173  -  CC-BY-4.0")
    c.drawRightString(W - M, M + 6, f"Page {page_num} of {total}")


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

def labeled_box(c, x, y, w, h, label, sublabel, foot, accent_stroke=False, gold_fill=False):
    stroke = ACCENT if accent_stroke else EDGE_P
    c.setStrokeColor(stroke); c.setLineWidth(0.8)
    if gold_fill:
        c.setFillColor(ACCENT); c.setFillAlpha(0.10)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1); c.setFillAlpha(1.0)
    else:
        c.setFillColor(BG); c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 6, y + h - 12, label)
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(x + 6, y + h - 23, sublabel)
    if foot:
        c.setFont("Helvetica", 5.5); c.setFillColor(INK_D if gold_fill else INK_F)
        c.drawString(x + 6, y + 5, foot)


# ─────────────────────────────────────────────────────────────
# PAGE 3 — CIRCULATORY (YAWAR blood)
# ─────────────────────────────────────────────────────────────

def page3_circulatory(c):
    setup(c)
    header(c, "AGENT ANATOMY — CIRCULATORY (YAWAR receipt bus)",
           "The blood. Append-only SHA-256 receipts. 20 SLOC on disk. Every component reads from YAWAR; only ceremonial writers commit.")

    # ── HEART (centered, top) — pumps receipts ──
    heart_w, heart_h = 260, 60
    heart_x = (W - heart_w) / 2
    heart_y = H - 150
    labeled_box(c, heart_x, heart_y, heart_w, heart_h,
                "HEART  -  YUYAY v3 (CRITIQUE GATE)",
                "13-axis conjunctive AND  ::  moral + measure >= 0.95",
                "yuyay_v3_heart/03_kernel.py  -  430 SLOC  -  pumps gated receipts",
                accent_stroke=True, gold_fill=True)

    # ── Vasculature: gold curved loops from heart down through page and back ──
    # Arterial side (LEFT) — heart -> RUWAY (write surface) -> peripherals -> back
    c.setStrokeColor(ACCENT); c.setLineWidth(1.5)
    # Out from heart (left descending)
    p = c.beginPath()
    p.moveTo(heart_x + 40, heart_y)
    p.curveTo(heart_x - 40, heart_y - 30, M + 30, heart_y - 80, M + 30, heart_y - 140)
    p.lineTo(M + 30, M + 100)
    c.drawPath(p, stroke=1, fill=0)
    # Back to heart (right ascending) — VENOUS return
    p = c.beginPath()
    p.moveTo(W - M - 30, M + 100)
    p.lineTo(W - M - 30, heart_y - 140)
    p.curveTo(W - M - 30, heart_y - 80, heart_x + heart_w + 40, heart_y - 30, heart_x + heart_w - 40, heart_y)
    c.drawPath(p, stroke=1, fill=0)

    # ── RUWAY write surface (only legal writer) — left side ──
    ruway_x, ruway_y = M + 60, heart_y - 80
    labeled_box(c, ruway_x, ruway_y, 180, 50,
                "RUWAY  -  ceremonial write",
                "Only D-YAWAR-FLOW-authorized writer",
                "writes pass through SENTRA inspection")

    # Capillary bed metaphor — receipts append at the periphery
    # Cluster of small dots representing receipt packets along left arterial line
    c.setFillColor(ACCENT)
    for i, frac in enumerate([0.25, 0.42, 0.58, 0.74]):
        cy = ruway_y - 30 - (i * 38)
        c.circle(M + 30, cy, 3, stroke=0, fill=1)
        c.setFont("Helvetica", 5.5); c.setFillColor(INK_D)
        c.drawString(M + 42, cy - 2, f"receipt {i+1}  ::  SHA-256(packet, sort_keys=True)")
        c.setFillColor(ACCENT)

    # ── YAWAR APPEND-ONLY LEDGER — right side, big visible block ──
    led_x, led_y, led_w, led_h = W - M - 240, heart_y - 200, 220, 240
    c.setStrokeColor(EDGE_P); c.setLineWidth(0.9)
    c.setFillColor(BG); c.rect(led_x, led_y, led_w, led_h, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(INK)
    c.drawString(led_x + 8, led_y + led_h - 14, "YAWAR  -  append-only ledger")
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(led_x + 8, led_y + led_h - 25, "yawar_bus.py  -  20 SLOC  -  immutable receipts")
    # Ledger row sketch
    c.setFont("Courier", 5.5); c.setFillColor(INK_F)
    rows = [
        ("r#001", "bacf5443...", "{layer:heart, gate_pass:1}"),
        ("r#002", "df4e9741...", "{layer:overwatch, alerts:0}"),
        ("r#003", "6381bc23...", "{layer:hatun-raid, cycle:42}"),
        ("r#004", "43f0c3a9...", "{layer:tupu-t7, tripwires:0/10}"),
        ("r#005", "ea65ddc5...", "{layer:qm, lam_min:0.231}"),
        ("r#006", "e9fac882...", "{layer:chakra-2, k:3, fixed}"),
        ("r#007", "<...growing...>", "{layer:rimay, energy:14.2}"),
    ]
    ry = led_y + led_h - 50
    for tag, h, payload in rows:
        c.drawString(led_x + 8,  ry, tag)
        c.setFillColor(ACCENT); c.drawString(led_x + 44, ry, h)
        c.setFillColor(INK_F);  c.drawString(led_x + 108, ry, payload)
        ry -= 11
    # Snapshot drawer (sub-block)
    c.setStrokeColor(EDGE_W); c.setDash(2,2)
    c.line(led_x + 8, led_y + 50, led_x + led_w - 8, led_y + 50); c.setDash()
    c.setFont("Helvetica-Bold", 7); c.setFillColor(INK)
    c.drawString(led_x + 8, led_y + 38, "snapshots[layer] -> frozen dict")
    c.setFont("Helvetica", 6); c.setFillColor(INK_D)
    c.drawString(led_x + 8, led_y + 28, "json.loads(json.dumps(data, default=str))")
    c.drawString(led_x + 8, led_y + 18, "agents READ snapshots, NEVER write")
    c.drawString(led_x + 8, led_y +  6, "D-YAWAR-FLOW enforced")

    # ── SENTRA gatekeeper inline on write path — between RUWAY and YAWAR ──
    sen_x, sen_y = (ruway_x + 200), ruway_y + 14
    c.setStrokeColor(IMMUNE_INK); c.setLineWidth(0.8)
    c.setFillColor(BG); c.roundRect(sen_x, sen_y, 110, 30, 4, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(IMMUNE_INK)
    c.drawString(sen_x + 6, sen_y + 18, "SENTRA inspect()")
    c.setFont("Helvetica", 5.5); c.setFillColor(INK_D)
    c.drawString(sen_x + 6, sen_y + 7, "18 SLOC  -  6 sigs + DoS guard")
    # arrow RUWAY -> SENTRA -> YAWAR
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.6)
    c.line(ruway_x + 180, ruway_y + 25, sen_x, sen_y + 15)
    c.line(sen_x + 110, sen_y + 15, led_x, led_y + led_h - 40)

    # ── Legend / receipt anatomy ──
    leg_y = M + 70
    c.setStrokeColor(EDGE_W); c.line(M, leg_y + 30, W - M, leg_y + 30)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(INK)
    c.drawString(M, leg_y + 18, "ANATOMY OF ONE RECEIPT  -  every write commits the same shape")
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(M, leg_y +  6,
        "h = sha256( json.dumps(packet, sort_keys=True, default=str) ).hexdigest()    ->    appended as {hash, packet} -- never mutated, never deleted")
    c.setFont("Helvetica", 6); c.setFillColor(INK_F)
    c.drawString(M, leg_y - 6,
        "Cross-process reproducibility holds when the packet body is timestamp-free; receipts that include _iso_now() are intra-run deterministic only (documented in musquy/00_RESULT.md).")

    footer(c, 1, 2)
    c.showPage()


# ─────────────────────────────────────────────────────────────
# PAGE 4 — IMMUNE SYSTEM
# ─────────────────────────────────────────────────────────────

def page4_immune(c):
    setup(c)
    header(c, "AGENT ANATOMY — IMMUNE SYSTEM (HUKLLA tripwires + SENTRA white cells)",
           "Two layers of defense. SENTRA inspects every outbound packet. HUKLLA fires the deadman if any of 10 invariants trip. No partial halt. No override.")

    # ── Top half: HUKLLA — the antibody memory grid ──
    # 10 tripwire nodes arranged in 2 rows × 5 columns
    tripwires = [
        ("T01", "MORAL_GROUNDING",          "moralGrounding < 0.95"),
        ("T02", "MEASURABILITY_HONESTY",    "measurability < 0.95"),
        ("T03", "EVAL_AWARENESS",           "'this is a test' signal"),
        ("T04", "DECEPTION_KEYWORDS",       "'manipulate' / 'deceive'"),
        ("T05", "UNAUTHORIZED_WRITE",       "write outside doctrine paths"),
        ("T06", "SPAWN_OUTSIDE_SANDBOX",    "process spawn outside sandbox"),
        ("T07", "UNAUTHORIZED_NETWORK",     "non-allowlisted endpoint"),
        ("T08", "SELF_CODE_MODIFY",         "Godel-machine self-edit"),
        ("T09", "CONFLICTING_DIRECTIVES",   "two live directives, no pick"),
        ("T10", "REVERSAL_DIRECTIVE",       "Stephen says STOP / abort"),
    ]
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(M, H - M - 50, "HUKLLA  -  10 deterministic tripwires (D45, conjunctive AND, deadman switch)")
    c.setFont("Helvetica", 7); c.setFillColor(INK_D)
    c.drawString(M, H - M - 62, "Any single fire -> allegiance_pass = False -> state frozen at pre-cycle value. Brain cannot reset. Only Stephen's new directive resets.")

    grid_top = H - M - 80
    cols, rows = 5, 2
    cell_w = (W - 2 * M - (cols - 1) * 8) / cols
    cell_h = 60
    for i, (tid, name, cond) in enumerate(tripwires):
        col = i % cols
        row = i // cols
        x = M + col * (cell_w + 8)
        y = grid_top - row * (cell_h + 8) - cell_h
        # Antibody-shaped cell: outer rounded rect + inner Y-glyph (simplified)
        c.setStrokeColor(IMMUNE_INK); c.setLineWidth(0.9)
        c.setFillColor(BG); c.roundRect(x, y, cell_w, cell_h, 4, stroke=1, fill=1)
        # Y-glyph antibody (top-left small)
        cx = x + 12; cy = y + cell_h - 12
        c.setStrokeColor(IMMUNE_INK); c.setLineWidth(1.2)
        c.line(cx, cy, cx - 5, cy + 8)
        c.line(cx, cy, cx + 5, cy + 8)
        c.line(cx, cy, cx, cy - 6)
        # ID + name
        c.setFont("Helvetica-Bold", 8); c.setFillColor(IMMUNE_INK)
        c.drawString(x + 24, y + cell_h - 14, tid)
        c.setFont("Helvetica-Bold", 6.5); c.setFillColor(INK)
        c.drawString(x + 24, y + cell_h - 24, name)
        c.setFont("Helvetica", 5.8); c.setFillColor(INK_D)
        # wrap condition into two lines if needed
        c.drawString(x + 6, y + 14, cond)
        c.setFont("Helvetica", 5.2); c.setFillColor(INK_F)
        c.drawString(x + 6, y + 5, "fire -> deadman -> halt cycle")

    # Deadman switch indicator under grid
    dm_y = grid_top - 2 * (cell_h + 8) - 28
    c.setStrokeColor(EDGE_P); c.setLineWidth(1.0)
    c.setFillColor(BG); c.rect(M, dm_y, W - 2*M, 22, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(INK)
    c.drawString(M + 8, dm_y + 12, "DEADMAN SWITCH")
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(M + 100, dm_y + 12,
        "checked conjunctively before AND after hatun() executes each cycle  ::  results cryptographically committed to continuum_hash receipt chain")

    # ── Bottom half: SENTRA — egress inspector / white blood cells ──
    sen_top_y = dm_y - 50
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(M, sen_top_y + 30,
        "SENTRA  -  egress inspector (white blood cells of the receipt bus)")
    c.setFont("Helvetica", 7); c.setFillColor(INK_D)
    c.drawString(M, sen_top_y + 18,
        "sentra_immune.py  -  18 SLOC on disk  -  inline gatekeeper on every YAWAR write call (Yawar.append refuses if sentra_inspect returns False)")

    # Left: the 6 threat signatures as antigen cards
    sig_x = M
    sigs = [
        ("DROP TABLE",  "SQL injection"),
        ("rm -rf",      "destructive shell"),
        ("<script",     "XSS / HTML inject"),
        ("eval(",       "arbitrary exec"),
        ("subprocess",  "process spawn"),
        ("../../etc",   "path traversal"),
    ]
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(INK)
    c.drawString(sig_x, sen_top_y, "6 threat signatures  (case-insensitive substring scan over str(packet).lower())")
    cw = (W/2 - 2*M) / 3
    ch = 34
    for i, (sig, what) in enumerate(sigs):
        col = i % 3
        row = i // 3
        x = sig_x + col * (cw + 6)
        y = sen_top_y - 12 - row * (ch + 6) - ch
        c.setStrokeColor(IMMUNE_INK); c.setLineWidth(0.7)
        c.setFillColor(BG); c.roundRect(x, y, cw, ch, 3, stroke=1, fill=1)
        c.setFont("Courier-Bold", 7.5); c.setFillColor(IMMUNE_INK)
        c.drawString(x + 6, y + ch - 12, sig)
        c.setFont("Helvetica", 5.8); c.setFillColor(INK_D)
        c.drawString(x + 6, y + 6, what)

    # Right: size-DoS guard + return semantics
    side_x = W/2 + 8
    side_y = sen_top_y - 12
    c.setStrokeColor(EDGE_P); c.setLineWidth(0.8)
    c.setFillColor(BG); c.rect(side_x, side_y - 80, W - M - side_x, 80, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
    c.drawString(side_x + 6, side_y - 12, "Additional guards")
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    lines = [
        "size DoS:  len(str(packet)) > 1_000_000  ->  reject",
        "return:    True  =  packet clears, write commits",
        "           False =  immune rejection, PermissionError",
        "expandable via sentra_signatures.json (codex pattern)",
        "preserves SENTRA's prior cyber/threat-intel job (P9)",
    ]
    ly = side_y - 24
    for ln in lines:
        c.drawString(side_x + 6, ly, "- " + ln); ly -= 11

    # Bottom note
    bn_y = M + 35
    c.setStrokeColor(EDGE_W); c.line(M, bn_y + 16, W - M, bn_y + 16)
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(INK)
    c.drawString(M, bn_y + 6, "WHAT THIS DIAGRAM IS NOT")
    c.setFont("Helvetica", 6); c.setFillColor(INK_D)
    c.drawString(M, bn_y - 4,
        "-  Not a biology model. \"White cells\" and \"antibodies\" are metaphors for inspection and tripwire fixtures.")
    c.drawString(M, bn_y - 13,
        "-  Not a substitute for a hardened WAF. SENTRA's 6 signatures are a doctrine prefilter, not a complete threat model; harden upstream too.")

    footer(c, 2, 2)
    c.showPage()


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    page3_circulatory(c)
    page4_immune(c)
    c.save()
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()
