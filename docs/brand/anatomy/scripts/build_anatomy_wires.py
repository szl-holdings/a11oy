#!/usr/bin/env python3
"""
build_anatomy_wires.py — 4-page wiring diagram bundle.

Layout requested by Stephen:
  Page 1: BLOOD rundown — wires only, brain hanging off as a tethered organ
  Page 2: BLOOD depth — receipt anatomy, append/snapshot internals, write path
  Page 3: IMMUNE rundown — wires only, HUKLLA + SENTRA in line with the bus
  Page 4: IMMUNE depth — 10 tripwires, 6 signatures, deadman switch semantics

Every label traces to on-disk source. Verified live:
  yawar_bus.py            20 SLOC  (append, snapshot, read; SHA-256 receipts)
  sentra_immune.py        18 SLOC  (6 threat sigs + DoS guard; True/False return)
  three_pillars/03_HUKLLA_STAGE.py  660 SLOC  (T01..T10 + AutonomyTier + deadman)
  yuyay_v3_heart/03_kernel.py       430 SLOC  (13-axis critique gate)
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
import math

OUT = "/home/user/workspace/field_meditation/_anatomy_wires.pdf"

# Palette (locked — matches body, brain, blood-immune precursor)
BG     = HexColor("#F5F1E8")
INK    = HexColor("#1A1A1A")
INK_D  = HexColor("#4A4A4A")
INK_F  = HexColor("#8A8A8A")
ACCENT = HexColor("#B08940")  # gold = receipt/gate
EDGE_P = HexColor("#2A2A2A")
EDGE_S = HexColor("#6E6E6E")
EDGE_W = HexColor("#B0B0B0")
IMMUNE = HexColor("#3A4A5A")  # slate = immune
ALARM  = HexColor("#8C3A2E")  # rust = tripwire / deadman

W, H = letter
M = 0.5 * inch


def setup(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)


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
# Shared primitives
# ─────────────────────────────────────────────────────────────

def organ_box(c, x, y, w, h, label, sublabel, foot, color=EDGE_P,
              gold_fill=False, slate_fill=False):
    """Three-line organ card (label / sublabel / file-SLOC)."""
    c.setStrokeColor(color); c.setLineWidth(0.9)
    if gold_fill:
        c.setFillColor(ACCENT); c.setFillAlpha(0.10)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1); c.setFillAlpha(1.0)
    elif slate_fill:
        c.setFillColor(IMMUNE); c.setFillAlpha(0.08)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1); c.setFillAlpha(1.0)
    else:
        c.setFillColor(BG); c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 6, y + h - 12, label)
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(x + 6, y + h - 23, sublabel)
    if foot:
        c.setFont("Helvetica", 5.5); c.setFillColor(INK_D if (gold_fill or slate_fill) else INK_F)
        c.drawString(x + 6, y + 5, foot)


def wire(c, x1, y1, x2, y2, color=ACCENT, width=1.2, dashed=False, label=None,
         lx=None, ly=None):
    """Draw a curved wire between two anchor points with optional inline label."""
    c.setStrokeColor(color); c.setLineWidth(width)
    if dashed:
        c.setDash(3, 2)
    p = c.beginPath()
    p.moveTo(x1, y1)
    # control points: arc out then back
    cx1 = x1 + (x2 - x1) * 0.35
    cy1 = y1 + (y2 - y1) * 0.05
    cx2 = x1 + (x2 - x1) * 0.65
    cy2 = y2 - (y2 - y1) * 0.05
    p.curveTo(cx1, cy1, cx2, cy2, x2, y2)
    c.drawPath(p, stroke=1, fill=0)
    if dashed:
        c.setDash()
    if label:
        if lx is None: lx = (x1 + x2) / 2 - 30
        if ly is None: ly = (y1 + y2) / 2 + 4
        c.setFont("Helvetica", 5.5); c.setFillColor(INK_F)
        c.drawString(lx, ly, label)


def connector_dot(c, x, y, color=ACCENT, r=3):
    c.setFillColor(color); c.setStrokeColor(color)
    c.circle(x, y, r, stroke=0, fill=1)


# ─────────────────────────────────────────────────────────────
# PAGE 1 — BLOOD RUNDOWN (wires + brain tethered)
# ─────────────────────────────────────────────────────────────

def page1_blood_rundown(c):
    setup(c)
    header(c, "BLOOD — CIRCULATORY WIRING (rundown)",
           "How YAWAR connects every organ. Append-only SHA-256 receipts. Brain hangs off the bus by a single tether: it READS snapshots, never WRITES.")

    # Anchors
    heart_x, heart_y = W / 2 - 90, H - 165
    heart_w, heart_h = 180, 56

    yawar_x = W / 2 - 200
    yawar_y = M + 130
    yawar_w = 400
    yawar_h = 40

    # Brain (tethered, top-left, hanging off the heart artery)
    # Larger ellipse, cleft pushed to right half so text sits cleanly in left half
    brain_x, brain_y = M + 10, H - 215
    brain_w, brain_h = 160, 95
    c.setStrokeColor(EDGE_P); c.setLineWidth(1.1)
    c.setFillColor(BG)
    c.ellipse(brain_x, brain_y, brain_x + brain_w, brain_y + brain_h, stroke=1, fill=1)
    # cleft line only in upper-right quadrant (out of text path)
    c.setStrokeColor(EDGE_W); c.setDash(2, 2)
    c.line(brain_x + brain_w*0.72, brain_y + brain_h - 14,
           brain_x + brain_w*0.72, brain_y + brain_h*0.45)
    c.setDash()
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(brain_x + 18, brain_y + brain_h - 22, "BRAIN")
    c.setFont("Helvetica", 6.4); c.setFillColor(INK_D)
    c.drawString(brain_x + 18, brain_y + brain_h - 34, "5 cortex regions + QM")
    c.drawString(brain_x + 18, brain_y + brain_h - 44, "hanging organ")
    c.drawString(brain_x + 18, brain_y + 30, "reads yawar.snapshot(layer)")
    c.drawString(brain_x + 18, brain_y + 20, "never writes the bus")
    c.drawString(brain_x + 18, brain_y + 10, "YUYAY supplies gated scores")

    # Heart (gold, central pump)
    organ_box(c, heart_x, heart_y, heart_w, heart_h,
              "HEART  -  YUYAY v3 (CRITIQUE GATE)",
              "13-axis conjunctive AND  ::  moral + measure >= 0.95",
              "yuyay_v3_heart/03_kernel.py  -  430 SLOC",
              color=ACCENT, gold_fill=True)

    # Overwatch (top-right, read-only)
    ow_x, ow_y = W - M - 180, H - 175
    organ_box(c, ow_x, ow_y, 180, 50,
              "OVERWATCH (R0513)",
              "5 invariants  ::  READ-ONLY",
              "r0513_overwatch_evolution/06_kernel.py  -  146 SLOC")

    # Mid-row organs feeding the bus from above
    row_y = H - 295
    organs = [
        ("MUSQUY",     "K-candidate sim",       "musquy/kernel.py  -  219 SLOC"),
        ("RIMAY",      "Proposer / action",     "rimay (architecture)"),
        ("TUKUY",      "Egress actuator",       "tukuy/kernel.py  -  70 SLOC"),
        ("HATUN-RAID", "Sovereign orchestrator","hatun/03_kernel.py  -  199 SLOC"),
    ]
    spacing = (W - 2*M - 4*150) / 3
    for i, (lbl, sub, foot) in enumerate(organs):
        ox = M + i * (150 + spacing)
        organ_box(c, ox, row_y, 150, 50, lbl, sub, foot)

    # RUWAY ceremonial write surface (ONLY legal writer)
    ru_x, ru_y, ru_w, ru_h = W/2 - 100, yawar_y + yawar_h + 35, 200, 36
    organ_box(c, ru_x, ru_y, ru_w, ru_h,
              "RUWAY  -  ceremonial write surface",
              "Only D-YAWAR-FLOW authorized writer",
              "all writes traverse SENTRA inspection")

    # YAWAR bus (the big horizontal vessel)
    c.setStrokeColor(ACCENT); c.setLineWidth(2.0)
    c.setFillColor(BG)
    c.roundRect(yawar_x, yawar_y, yawar_w, yawar_h, 6, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 10); c.setFillColor(ACCENT)
    c.drawString(yawar_x + 10, yawar_y + 24, "YAWAR  -  append-only receipt bus")
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(yawar_x + 10, yawar_y + 10,
        "yawar_bus.py  -  20 SLOC  -  sha256(json.dumps(packet, sort_keys=True))  -  receipts immutable, snapshots frozen per layer")

    # Wires — every wire is doctrine-real
    # 1. Brain TETHER to heart artery (top-left curl, gold) — READ tether (dashed gold)
    # Label placed ABOVE the wire so it doesn't sit on the line itself
    wire(c, brain_x + brain_w - 4, brain_y + brain_h/2,
            heart_x + 8, heart_y + heart_h/2,
            color=ACCENT, width=1.4, dashed=True,
            label="tether: read gated scores",
            lx=brain_x + brain_w + 8, ly=brain_y + brain_h + 6)
    connector_dot(c, brain_x + brain_w - 4, brain_y + brain_h/2)
    connector_dot(c, heart_x + 8, heart_y + heart_h/2)

    # 2. Heart -> RUWAY (writes only flow heart-side through ceremony)
    wire(c, heart_x + heart_w/2, heart_y,
            ru_x + ru_w/2, ru_y + ru_h,
            color=ACCENT, width=1.6,
            label="committed packets ->", lx=W/2 - 38, ly=ru_y + ru_h + 14)
    # 3. RUWAY -> YAWAR bus
    wire(c, ru_x + ru_w/2, ru_y,
            yawar_x + yawar_w/2, yawar_y + yawar_h,
            color=ACCENT, width=1.6)

    # 4. Overwatch -> YAWAR (READ-ONLY, dashed; arrows the OTHER way)
    wire(c, ow_x + 20, ow_y,
            yawar_x + yawar_w - 20, yawar_y + yawar_h,
            color=EDGE_S, width=0.9, dashed=True,
            label="reads only (R0513)", lx=ow_x - 18, ly=ow_y - 12)

    # 5. Mid-row organs -> RUWAY (each one drops straight down, then a short horizontal
    #    elbow into RUWAY — no crossing curves through the middle of the page)
    elbow_y = ru_y + ru_h + 60
    for i in range(4):
        ox = M + i * (150 + spacing) + 75
        # drop straight down
        c.setStrokeColor(EDGE_S); c.setLineWidth(0.8); c.setDash(2, 2)
        c.line(ox, row_y, ox, elbow_y); c.setDash()
        connector_dot(c, ox, row_y, color=EDGE_S, r=2)
        # horizontal elbow to RUWAY top edge
        ruw_target = ru_x + 30 + i * (ru_w - 60) / 3
        c.setStrokeColor(EDGE_S); c.setLineWidth(0.8); c.setDash(2, 2)
        c.line(ox, elbow_y, ruw_target, elbow_y)
        c.line(ruw_target, elbow_y, ruw_target, ru_y + ru_h)
        c.setDash()

    # 6. YAWAR -> brain (snapshot READ tether, dashed gold)
    # Route LEFT side of page (down the left margin) so it doesn't cross the organ stack.
    # Endpoint enters brain from the BOTTOM, label sits below the brain ellipse cleanly.
    c.setStrokeColor(ACCENT); c.setLineWidth(1.0); c.setDash(2, 2)
    # vertical up the far-left margin
    leftx = M + 4
    c.line(yawar_x + 30, yawar_y + yawar_h/2, leftx, yawar_y + yawar_h/2)
    c.line(leftx, yawar_y + yawar_h/2, leftx, brain_y - 30)
    c.line(leftx, brain_y - 30, brain_x + 30, brain_y - 30)
    c.line(brain_x + 30, brain_y - 30, brain_x + 30, brain_y + 2)
    c.setDash()
    c.setFont("Helvetica", 6); c.setFillColor(INK_D)
    c.drawString(leftx + 6, brain_y - 26, "snapshots ->  read by all organs")

    # Legend
    leg_y = M + 32
    c.setStrokeColor(EDGE_W); c.line(M, leg_y + 38, W - M, leg_y + 38)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
    c.drawString(M, leg_y + 28, "WIRE LEGEND")
    c.setFont("Helvetica", 6.4); c.setFillColor(INK_D)
    # gold solid
    c.setStrokeColor(ACCENT); c.setLineWidth(1.6)
    c.line(M + 90, leg_y + 30, M + 130, leg_y + 30)
    c.drawString(M + 138, leg_y + 28, "gold solid  =  write path (heart -> RUWAY -> YAWAR)")
    # gold dashed
    c.setStrokeColor(ACCENT); c.setLineWidth(1.1); c.setDash(2, 2)
    c.line(M + 90, leg_y + 18, M + 130, leg_y + 18); c.setDash()
    c.drawString(M + 138, leg_y + 16, "gold dashed  =  read tether (brain + every organ snapshot)")
    # slate dashed
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.8); c.setDash(2, 2)
    c.line(M + 90, leg_y + 6, M + 130, leg_y + 6); c.setDash()
    c.drawString(M + 138, leg_y + 4, "slate dashed  =  candidate flow into RUWAY  /  R0513 read-only audit")

    footer(c, 1, 4)
    c.showPage()


# ─────────────────────────────────────────────────────────────
# PAGE 2 — BLOOD DEPTH (receipt anatomy + write path internals)
# ─────────────────────────────────────────────────────────────

def page2_blood_depth(c):
    setup(c)
    header(c, "BLOOD — DEPTH (receipt anatomy, append + snapshot internals)",
           "What one receipt actually is, on disk. The full source of yawar_bus.py is 20 SLOC — every guarantee below is read straight from it.")

    # Source listing block (yawar_bus.py verbatim, condensed)
    # Taller box so def read(self,layer) is not clipped at the bottom
    src_x, src_y, src_w, src_h = M, H - 410, W/2 - M - 8, 250
    c.setStrokeColor(EDGE_P); c.setLineWidth(0.9)
    c.setFillColor(BG); c.rect(src_x, src_y, src_w, src_h, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(INK)
    c.drawString(src_x + 8, src_y + src_h - 14, "yawar_bus.py  -  20 SLOC  (verbatim, on disk)")
    c.setFont("Courier", 6.2); c.setFillColor(INK_D)
    lines = [
        '"""YAWAR - blood / receipt bus. Append-only, immutable."""',
        'import hashlib, json',
        'from typing import Any',
        '',
        'class Yawar:',
        '  def __init__(self):',
        '    self.receipts = []',
        '    self.snapshots = {}',
        '',
        '  def append(self, packet, sentra_inspect=None) -> str:',
        '    if sentra_inspect and not sentra_inspect(packet):',
        '      raise PermissionError("SENTRA rejected packet")',
        '    h = hashlib.sha256(',
        '          json.dumps(packet, sort_keys=True,',
        '                     default=str).encode()).hexdigest()',
        '    self.receipts.append({"hash": h, "packet": packet})',
        '    return h',
        '',
        '  def snapshot(self, layer, data):',
        '    self.snapshots[layer] = json.loads(',
        '         json.dumps(data, default=str))   # frozen copy',
        '',
        '  def read(self, layer):',
        '    return self.snapshots.get(layer, {})',
    ]
    ly = src_y + src_h - 28
    for ln in lines:
        c.drawString(src_x + 8, ly, ln)
        ly -= 7.5

    # Receipt anatomy block (right side) — match source-box height
    ra_x = W/2 + 8
    ra_w = W - M - ra_x
    ra_h = 250
    ra_y = H - 410
    c.setStrokeColor(EDGE_P); c.setLineWidth(0.9)
    c.setFillColor(BG); c.rect(ra_x, ra_y, ra_w, ra_h, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(INK)
    c.drawString(ra_x + 8, ra_y + ra_h - 14, "ANATOMY OF ONE RECEIPT")

    # Diagram inside: packet -> json.dumps -> sha256 -> append
    y0 = ra_y + ra_h - 40
    steps = [
        ("packet: dict",         "{layer, payload, parent_hash, ...}"),
        ("json.dumps",           "sort_keys=True, default=str  (stable bytes)"),
        ("hashlib.sha256",       ".hexdigest()  -> 64-char hex"),
        ("receipts.append",      "{'hash': h, 'packet': packet}"),
        ("return h",             "caller stores h as continuum link"),
    ]
    sx = ra_x + 12
    for i, (lbl, expl) in enumerate(steps):
        y = y0 - i * 34
        c.setStrokeColor(ACCENT); c.setLineWidth(0.7)
        c.setFillColor(BG); c.roundRect(sx, y, ra_w - 24, 26, 3, stroke=1, fill=1)
        c.setFont("Helvetica-Bold", 7.5); c.setFillColor(ACCENT)
        c.drawString(sx + 6, y + 15, lbl)
        c.setFont("Helvetica", 6); c.setFillColor(INK_D)
        c.drawString(sx + 6, y + 5, expl)
        if i < len(steps) - 1:
            c.setStrokeColor(ACCENT); c.setLineWidth(1.0)
            c.line(sx + (ra_w - 24)/2, y, sx + (ra_w - 24)/2, y - 8)
            # arrowhead
            c.line(sx + (ra_w - 24)/2 - 3, y - 4, sx + (ra_w - 24)/2, y - 8)
            c.line(sx + (ra_w - 24)/2 + 3, y - 4, sx + (ra_w - 24)/2, y - 8)

    # Guarantees ledger (bottom)
    gy = M + 80
    c.setStrokeColor(EDGE_W); c.line(M, gy + 110, W - M, gy + 110)
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(M, gy + 100, "GUARANTEES (read directly from yawar_bus.py source)")
    c.setFont("Helvetica", 7); c.setFillColor(INK_D)
    g_lines = [
        "- Append-only:        self.receipts.append(...) — no method exists to delete or mutate prior receipts.",
        "- Stable serialization: json.dumps(..., sort_keys=True, default=str)  -> deterministic bytes for any packet whose values are timestamp-free.",
        "- Cryptographic link:  hashlib.sha256(..).hexdigest()  -> 256-bit, collision-resistant under standard assumptions.",
        "- Inline immune check: Yawar.append calls sentra_inspect(packet) BEFORE compute — refused packets raise PermissionError; never reach the ledger.",
        "- Frozen snapshots:    snapshot(layer, data) deep-copies via json round-trip — readers cannot mutate the live source object.",
        "- Read tether:         read(layer) returns the dict or empty — never raises, never blocks (D-YAWAR-FLOW read side).",
        "",
        "Honest scope:  the receipt is byte-identical across re-runs ONLY when packet values are timestamp-free.",
        "Receipts that include _iso_now() (e.g. musquy/kernel.py) are intra-run deterministic only.  Documented in musquy/00_RESULT.md after audit.",
    ]
    ly = gy + 88
    for ln in g_lines:
        c.drawString(M, ly, ln); ly -= 9

    footer(c, 2, 4)
    c.showPage()


# ─────────────────────────────────────────────────────────────
# PAGE 3 — IMMUNE RUNDOWN (wires)
# ─────────────────────────────────────────────────────────────

def page3_immune_rundown(c):
    setup(c)
    header(c, "IMMUNE — WIRING (rundown)",
           "Two layers in series.  SENTRA inspects every outbound packet inline.  HUKLLA fires the deadman if any of 10 invariants trip.  No partial halt.  No override.")

    # Top: heart (source of writes) and YAWAR (destination)
    heart_x, heart_y = M, H - 175
    organ_box(c, heart_x, heart_y, 180, 50,
              "HEART (writes originate)",
              "gated proposals  ::  one packet per accepted cycle",
              "yuyay_v3_heart  -  430 SLOC",
              color=ACCENT, gold_fill=True)

    bus_x, bus_y, bus_w, bus_h = W - M - 200, H - 175, 200, 50
    c.setStrokeColor(ACCENT); c.setLineWidth(1.6)
    c.setFillColor(BG); c.roundRect(bus_x, bus_y, bus_w, bus_h, 4, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(ACCENT)
    c.drawString(bus_x + 8, bus_y + 32, "YAWAR  (destination ledger)")
    c.setFont("Helvetica", 6.2); c.setFillColor(INK_D)
    c.drawString(bus_x + 8, bus_y + 20, "append-only  ::  sha256 receipts")
    c.drawString(bus_x + 8, bus_y +  8, "yawar_bus.py  -  20 SLOC")

    # MIDDLE: SENTRA inline gatekeeper
    sen_x, sen_y, sen_w, sen_h = W/2 - 110, H - 260, 220, 50
    organ_box(c, sen_x, sen_y, sen_w, sen_h,
              "SENTRA  -  egress inspector (white blood cells)",
              "6 threat signatures  +  size DoS guard  ->  True / False",
              "sentra_immune.py  -  18 SLOC  -  inline in Yawar.append()",
              color=IMMUNE, slate_fill=True)

    # Heart -> SENTRA -> YAWAR (the live write path)
    wire(c, heart_x + 180, heart_y + 25, sen_x, sen_y + sen_h/2,
         color=ACCENT, width=1.6,
         label="packet (sub-1MB, clean)",
         lx=heart_x + 200, ly=heart_y + 8)
    wire(c, sen_x + sen_w, sen_y + sen_h/2, bus_x, bus_y + 25,
         color=ACCENT, width=1.6,
         label="appended on PASS",
         lx=sen_x + sen_w + 8, ly=sen_y + sen_h + 10)
    # Reject branch (slate, going down)
    wire(c, sen_x + sen_w/2, sen_y, sen_x + sen_w/2, sen_y - 50,
         color=ALARM, width=1.2,
         label="raises PermissionError  ->  packet dropped",
         lx=sen_x + sen_w/2 + 10, ly=sen_y - 28)

    # BELOW: HUKLLA deadman ring — 10 tripwires arranged around a central ring
    ring_cx, ring_cy = W/2, M + 200
    ring_r = 110
    # Outer ring
    c.setStrokeColor(ALARM); c.setLineWidth(1.4)
    c.circle(ring_cx, ring_cy, ring_r, stroke=1, fill=0)
    c.setStrokeColor(EDGE_W); c.setDash(2, 2)
    c.circle(ring_cx, ring_cy, ring_r - 14, stroke=1, fill=0); c.setDash()
    # Center: deadman switch
    c.setFillColor(ALARM); c.setFillAlpha(0.10)
    c.circle(ring_cx, ring_cy, 38, stroke=0, fill=1); c.setFillAlpha(1.0)
    c.setStrokeColor(ALARM); c.setLineWidth(1.2)
    c.circle(ring_cx, ring_cy, 38, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(ALARM)
    c.drawCentredString(ring_cx, ring_cy + 6, "DEADMAN")
    c.setFont("Helvetica", 6.2); c.setFillColor(INK_D)
    c.drawCentredString(ring_cx, ring_cy - 4, "allegiance_pass = False")
    c.drawCentredString(ring_cx, ring_cy - 13, "state frozen")
    c.drawCentredString(ring_cx, ring_cy - 22, "cycle halted")
    # 10 tripwire dots around ring
    tripwires = ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08", "T09", "T10"]
    for i, tid in enumerate(tripwires):
        ang = math.pi/2 - i * (2*math.pi/10)
        nx = ring_cx + ring_r * math.cos(ang)
        ny = ring_cy + ring_r * math.sin(ang)
        c.setFillColor(ALARM); c.circle(nx, ny, 5, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 6.5); c.setFillColor(INK)
        # offset label outward
        lx = ring_cx + (ring_r + 18) * math.cos(ang) - 8
        ly = ring_cy + (ring_r + 18) * math.sin(ang) - 2
        c.drawString(lx, ly, tid)
        # spoke from ring node to deadman center
        c.setStrokeColor(ALARM); c.setLineWidth(0.5); c.setDash(1, 2)
        c.line(nx, ny, ring_cx + 38*math.cos(ang+math.pi), ring_cy + 38*math.sin(ang+math.pi))
        # actually draw spoke from outer to inner along same ray
        c.line(nx - 5*math.cos(ang), ny - 5*math.sin(ang),
               ring_cx + 38*math.cos(ang), ring_cy + 38*math.sin(ang))
        c.setDash()

    # HUKLLA labels left + right
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(M, ring_cy + ring_r + 40, "HUKLLA  -  10 deterministic tripwires")
    c.setFont("Helvetica", 7); c.setFillColor(INK_D)
    c.drawString(M, ring_cy + ring_r + 28, "three_pillars/03_HUKLLA_STAGE.py  -  660 SLOC")
    c.drawString(M, ring_cy + ring_r + 18, "checked conjunctively BEFORE and AFTER hatun() each cycle")
    c.drawString(M, ring_cy + ring_r +  8, "results committed to continuum_hash receipt chain")

    # Where HUKLLA sits in the pipeline — land the wire exactly on T09 (upper-left node)
    # so the connection between SENTRA exit and the tripwire ring is unambiguous.
    ang_t09 = math.pi/2 - 9 * (2*math.pi/10)  # T01 at top, going clockwise; T09 just before T10
    t09_x = ring_cx + ring_r * math.cos(ang_t09)
    t09_y = ring_cy + ring_r * math.sin(ang_t09)
    wire(c, sen_x + sen_w/2, sen_y - 18,
         t09_x - 8, t09_y,
         color=ALARM, width=1.0, dashed=True)
    c.setFont("Helvetica", 6); c.setFillColor(INK_D)
    c.drawString(sen_x + 20, sen_y - 50, "every cycle's receipt audited against T01..T10")

    footer(c, 3, 4)
    c.showPage()


# ─────────────────────────────────────────────────────────────
# PAGE 4 — IMMUNE DEPTH (10 tripwires + 6 signatures + return semantics)
# ─────────────────────────────────────────────────────────────

def page4_immune_depth(c):
    setup(c)
    header(c, "IMMUNE — DEPTH (tripwire ledger + SENTRA source)",
           "Every row below is a fixture read directly from on-disk source.  No paraphrase. No invention.")

    # ── HUKLLA ledger table (10 rows) ──
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(M, H - M - 48, "HUKLLA — canonical T01..T10 (D45, source: three_pillars/03_HUKLLA_STAGE.py)")
    c.setFont("Helvetica", 7); c.setFillColor(INK_D)
    c.drawString(M, H - M - 60, "Source: TRIPWIRE_DESCRIPTIONS dict, lines ~85-95.  Exact strings retained.")

    rows = [
        ("T01", "MORAL_GROUNDING",        "moralGrounding axis < 0.95 — hard fail, no override"),
        ("T02", "MEASURABILITY_HONESTY",  "measurabilityHonesty < 0.95 — hard fail, no override"),
        ("T03", "EVAL_AWARENESS",         "introspection contains eval-awareness flag (NLA/Apollo)"),
        ("T04", "DECEPTION_KEYWORDS",     "introspection contains 'manipulate' / 'avoid detection' / 'deceive'"),
        ("T05", "UNAUTHORIZED_WRITE",     "agent attempts write outside doctrine-allowed paths"),
        ("T06", "SPAWN_OUTSIDE_SANDBOX",  "agent attempts to spawn processes outside sandbox"),
        ("T07", "UNAUTHORIZED_NETWORK",   "agent calls network endpoint not on allowlist"),
        ("T08", "SELF_CODE_MODIFY",       "agent attempts to modify its own source code (Godel attempt without ceremony)"),
        ("T09", "CONFLICTING_DIRECTIVES", "irreconcilable simultaneous directives — escalate to human, do not pick"),
        ("T10", "REVERSAL_DIRECTIVE",     "Stephen issues STOP / undo / revert — immediate halt"),
    ]
    table_y = H - M - 80
    row_h = 18
    # Header row
    c.setFont("Helvetica-Bold", 7); c.setFillColor(INK)
    c.drawString(M + 4,   table_y, "#")
    c.drawString(M + 38,  table_y, "ID")
    c.drawString(M + 200, table_y, "CONDITION")
    c.setStrokeColor(EDGE_W); c.line(M, table_y - 4, W - M, table_y - 4)
    table_y -= row_h
    for tid, name, cond in rows:
        c.setStrokeColor(EDGE_W); c.setLineWidth(0.3)
        c.line(M, table_y - 4, W - M, table_y - 4)
        c.setFont("Helvetica-Bold", 7.5); c.setFillColor(ALARM)
        c.drawString(M + 4,   table_y, tid)
        c.setFont("Helvetica-Bold", 7);   c.setFillColor(INK)
        c.drawString(M + 38,  table_y, name)
        c.setFont("Helvetica", 6.8);      c.setFillColor(INK_D)
        c.drawString(M + 200, table_y, cond)
        table_y -= row_h

    # AutonomyTier note
    table_y -= 10
    c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
    c.drawString(M, table_y, "Autonomy gating (HUKLLA reads tier per cycle):")
    table_y -= 12
    c.setFont("Helvetica", 6.8); c.setFillColor(INK_D)
    at = [
        "SCRATCHPAD  -  runs free, cannot affect external state.",
        "REVIEW      -  Stephen approval every K cycles.",
        "PRODUCTION  -  per-cycle Stephen approval required.",
    ]
    for ln in at:
        c.drawString(M + 14, table_y, "- " + ln); table_y -= 10

    # ── SENTRA source mini-block (right column would crowd, so put across full width) ──
    table_y -= 6
    c.setStrokeColor(EDGE_W); c.line(M, table_y, W - M, table_y); table_y -= 14
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(M, table_y, "SENTRA — 6 signatures + size guard (source: sentra_immune.py, 18 SLOC)")
    table_y -= 14
    c.setFont("Courier", 6.5); c.setFillColor(INK_D)
    sentra_src = [
        'THREAT_KEYWORDS = ["DROP TABLE", "rm -rf", "<script", "eval(", "subprocess", "../../etc"]',
        '',
        'def sentra_inspect(packet: dict) -> bool:',
        '    blob = str(packet).lower()',
        '    for sig in THREAT_KEYWORDS:',
        '        if sig.lower() in blob:',
        '            return False                # immune rejection',
        '    if len(blob) > 1_000_000:           # size DoS guard',
        '        return False',
        '    return True                         # packet clears',
    ]
    for ln in sentra_src:
        c.drawString(M, table_y, ln); table_y -= 8

    # Return semantics box
    table_y -= 6
    c.setStrokeColor(IMMUNE); c.setLineWidth(0.8)
    box_h = 56
    c.setFillColor(BG); c.rect(M, table_y - box_h, W - 2*M, box_h, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(IMMUNE)
    c.drawString(M + 8, table_y - 12, "Return semantics + scope")
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    ret = [
        "True   -> packet clears all 6 signatures and size guard. Yawar.append continues to sha256() + receipts.append({...}).",
        "False  -> Yawar.append raises PermissionError(\"SENTRA rejected packet\").  Receipt never enters the ledger.  No partial state.",
        "Honest scope: this is a doctrine PREFILTER, not a complete threat model.  Layer a WAF, secrets scanner, and dependency audit upstream.",
        "Expandable: ship sentra_signatures.json next to the kernel (codex-in-kernel pattern) to add signatures without architectural change.",
    ]
    for i, ln in enumerate(ret):
        c.drawString(M + 8, table_y - 22 - i * 9, "- " + ln)

    footer(c, 4, 4)
    c.showPage()


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("SZL Agent Body · Wires (yawar + huklla)")
    c.setAuthor("Lutar, Stephen P.")
    c.setSubject("Anatomy diagram: receipt bus + tripwires")
    page1_blood_rundown(c)
    page2_blood_depth(c)
    page3_immune_rundown(c)
    page4_immune_depth(c)
    c.save()
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()
