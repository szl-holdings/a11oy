#!/usr/bin/env python3
"""
build_anatomy_nervous.py — anatomy_nervous.{pdf,png}

The NERVOUS SYSTEM represents OTel/VSP span propagation:
how trace context flows through the agent body as signal.
License: Apache-2.0 (code)  |  CC-BY-4.0 (figure output)
Byline: Lutar, Stephen P. — SZL Holdings
"""
import math
import subprocess
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

OUT_PDF = "/home/user/workspace/evolution_pod/finish/anatomy/figures/anatomy_nervous.pdf"
OUT_PNG = "/home/user/workspace/evolution_pod/finish/anatomy/figures/anatomy_nervous.png"

# ── Palette (LOCKED) ──────────────────────────────────────────────────────────
BG      = HexColor("#F5F1E8")
INK     = HexColor("#1A1A1A")
INK_D   = HexColor("#4A4A4A")
INK_F   = HexColor("#8A8A8A")
ACCENT  = HexColor("#B08940")
EDGE_P  = HexColor("#2A2A2A")
EDGE_S  = HexColor("#6E6E6E")
EDGE_W  = HexColor("#B0B0B0")
NERVE   = HexColor("#4A7BA8")   # cool blue for signal propagation
NERVE_L = HexColor("#8BBAD4")   # lighter nerve

W, H = letter
M = 0.5 * inch


def setup(c):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def header(c):
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(INK)
    c.drawString(M, H - M - 6, "AGENT ANATOMY — NERVOUS SYSTEM (OTel/VSP span propagation)")
    c.setFont("Helvetica", 8)
    c.setFillColor(INK_D)
    c.drawString(M, H - M - 20,
        "Signal flow. Trace context (trace_id, span_id, parent_span_id) propagates from brain "
        "through every effector. Every receipt carries its span lineage.")
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


def span_node(c, x, y, w, h, label, span_id, kind, children=0):
    """Draw a span node (represents one OTel span)."""
    is_root = kind == "root"
    is_gate = kind == "gate"
    stroke = ACCENT if is_root else (NERVE if is_gate else EDGE_S)
    lw = 1.2 if is_root else 0.7
    c.setStrokeColor(stroke)
    c.setLineWidth(lw)
    if is_root:
        c.setFillColor(ACCENT)
        c.setFillAlpha(0.10)
    elif is_gate:
        c.setFillColor(NERVE)
        c.setFillAlpha(0.08)
    else:
        c.setFillColor(BG)
        c.setFillAlpha(1.0)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    c.setFillAlpha(1.0)

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(ACCENT if is_root else (NERVE if is_gate else INK))
    c.drawString(x + 6, y + h - 12, label)
    c.setFont("Courier", 5.8)
    c.setFillColor(INK_F)
    c.drawString(x + 6, y + h - 22, span_id)
    if children:
        c.setFont("Helvetica", 5.5)
        c.setFillColor(INK_F)
        c.drawRightString(x + w - 4, y + 5, f"{children} child spans")


def draw_nerve(c, x1, y1, x2, y2, is_primary=True):
    """Draw a nerve/signal pathway with slight curve."""
    c.setStrokeColor(NERVE if is_primary else NERVE_L)
    c.setLineWidth(1.0 if is_primary else 0.6)
    p = c.beginPath()
    p.moveTo(x1, y1)
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    ctrl_x = mid_x + (y2 - y1) * 0.15
    ctrl_y = mid_y - (x2 - x1) * 0.08
    p.curveTo(ctrl_x, ctrl_y, ctrl_x, ctrl_y, x2, y2)
    c.drawPath(p, stroke=1, fill=0)
    # Signal direction chevron
    angle = math.atan2(y2 - y1, x2 - x1)
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    size = 4
    c.setFillColor(NERVE if is_primary else NERVE_L)
    p2 = c.beginPath()
    p2.moveTo(mx + size * math.cos(angle), my + size * math.sin(angle))
    p2.lineTo(mx + size * math.cos(angle + 2.4), my + size * math.sin(angle + 2.4))
    p2.lineTo(mx + size * math.cos(angle - 2.4), my + size * math.sin(angle - 2.4))
    p2.close()
    c.drawPath(p2, stroke=0, fill=1)


def page1(c):
    setup(c)
    header(c)

    # ── SPAN HIERARCHY DIAGRAM ────────────────────────────────────────────────
    # Root span at top — HATUN cycle
    # Children: BRAIN propose → HEART gate → YAWAR commit → effector spans

    top_y     = H - M - 40
    node_w    = 200
    node_h    = 42
    node_gap  = 14

    # ROOT SPAN
    root_x = (W - node_w) / 2
    root_y = top_y - node_h
    span_node(c, root_x, root_y, node_w, node_h,
              "HATUN sovereign cycle",
              "trace_id=a3f8c2b1  span_id=0001  parent=ROOT",
              "root", children=4)

    # Level 2: four parallel spans
    l2_spans = [
        ("AMARU·BRAIN propose",   "span_id=0010  parent=0001", "gate"),
        ("YUYAY·HEART gate",      "span_id=0020  parent=0001", "gate"),
        ("YAWAR·receipt commit",  "span_id=0030  parent=0001", "normal"),
        ("RIMAY·output filter",   "span_id=0040  parent=0001", "normal"),
    ]
    l2_w = (W - 2*M - 3*node_gap) / 4
    l2_y = root_y - node_h - 30

    for i, (label, span_id, kind) in enumerate(l2_spans):
        lx = M + i * (l2_w + node_gap)
        span_node(c, lx, l2_y, l2_w, node_h, label, span_id, kind)
        # Nerve from root to this span
        draw_nerve(c,
                   root_x + (i + 0.5) * (node_w / 4), root_y,
                   lx + l2_w / 2, l2_y + node_h,
                   is_primary=(kind == "gate"))

    # Level 3: SENTRA + OVERWATCH as leaf spans under HEART and YAWAR
    l3_y = l2_y - node_h - 22
    l3_spans_under = [
        (1, "SENTRA·inspect()",   "span_id=0021  parent=0020", "gate"),
        (2, "R0513·OVERWATCH",    "span_id=0031  parent=0030", "normal"),
    ]
    l3_w = l2_w * 0.9

    for parent_idx, label, span_id, kind in l3_spans_under:
        px = M + parent_idx * (l2_w + node_gap)
        lx = px + (l2_w - l3_w) / 2
        span_node(c, lx, l3_y, l3_w, node_h, label, span_id, kind)
        draw_nerve(c, px + l2_w/2, l2_y, lx + l3_w/2, l3_y + node_h, is_primary=True)

    # ── VSP CONTEXT PROPAGATION BOX ──────────────────────────────────────────
    ctx_y = l3_y - 70
    ctx_w = W - 2*M
    c.setStrokeColor(NERVE)
    c.setLineWidth(0.9)
    c.setFillColor(NERVE)
    c.setFillAlpha(0.05)
    c.roundRect(M, ctx_y, ctx_w, 58, 5, stroke=1, fill=1)
    c.setFillAlpha(1.0)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(NERVE)
    c.drawString(M + 8, ctx_y + 46, "VSP CONTEXT WIRE  —  propagated on every inter-service call")
    c.setFont("Courier", 7)
    c.setFillColor(INK_D)
    c.drawString(M + 8, ctx_y + 32,
        "W3C-TraceContext:   traceparent: 00-{trace_id}-{span_id}-01")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(INK_F)
    c.drawString(M + 8, ctx_y + 20,
        "Each span on receipt commit appends { trace_id, span_id, parent_span_id, service, op, duration_ms } to YAWAR.")
    c.drawString(M + 8, ctx_y + 10,
        "Replay verifier checks span lineage: child.parent_span_id == parent.span_id for all n spans in a cycle receipt chain.")

    # ── SIGNAL TAXONOMY ───────────────────────────────────────────────────────
    tax_y = ctx_y - 65
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(INK)
    c.drawString(M, tax_y + 50, "SIGNAL TAXONOMY  —  three nerve classes")

    classes = [
        (ACCENT,  "EFFERENT (motor)",  "Brain → effectors. Carries gate decision + proposal payload. Spans: HATUN→AMARU→YUYAY."),
        (NERVE,   "AFFERENT (sensory)", "Effectors → brain. Carries receipts + gate scores back for next cycle. Spans: YAWAR→HATUN."),
        (EDGE_S,  "PROPRIOCEPTIVE",    "Self-monitoring. OVERWATCH + R0513 read own receipts to detect drift. Spans: R0513→HATUN."),
    ]
    for i, (col, cls, desc) in enumerate(classes):
        cy = tax_y + 30 - i * 20
        c.setFillColor(col)
        c.circle(M + 8, cy + 4, 4, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(INK)
        c.drawString(M + 18, cy + 6, cls)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(INK_D)
        c.drawString(M + 18, cy - 2, desc)

    # ── REFLEX ARC NOTE ───────────────────────────────────────────────────────
    ref_y = M + 52
    c.setStrokeColor(EDGE_W)
    c.line(M, ref_y + 16, W - M, ref_y + 16)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(INK)
    c.drawString(M, ref_y + 5, "DEADMAN REFLEX ARC")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(INK_D)
    c.drawString(M + 120, ref_y + 5,
        "HUKLLA tripwire fires → span context frozen at pre-cycle value → halt signal injected into HATUN root span → "
        "all child spans cancelled. No partial-commit. Span chain is evidence of the halt.")

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
