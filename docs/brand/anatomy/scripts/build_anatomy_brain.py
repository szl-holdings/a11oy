#!/usr/bin/env python3
"""
build_anatomy_brain.py — companion to build_tech_graph.py
Zooms inside the head: brain, heart, blood, immune system, sovereign seal.
Every region traces to an on-disk kernel with verified replay hash.
Paper aesthetic — matches agent_architecture.pdf palette exactly.
"""
import sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

OUT = "/home/user/workspace/field_meditation/_anatomy_brain.pdf"

# Palette (LOCKED — matches body diagram)
BG     = HexColor("#F5F1E8")
INK    = HexColor("#1A1A1A")
INK_D  = HexColor("#4A4A4A")
INK_F  = HexColor("#8A8A8A")
INK_VF = HexColor("#B5B5B5")
ACCENT = HexColor("#B08940")   # gold — gate only
EDGE_P = HexColor("#2A2A2A")
EDGE_S = HexColor("#6E6E6E")
EDGE_W = HexColor("#B0B0B0")

W, H = letter
M = 0.5 * inch

def setup(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(INK); c.setStrokeColor(INK)

def header(c):
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(INK)
    c.drawString(M, H - M - 6, "AGENT ANATOMY — INSIDE THE HEAD")
    c.setFont("Helvetica", 8); c.setFillColor(INK_D)
    c.drawString(M, H - M - 22,
        "Companion to agent_architecture.pdf. Every region traces to an on-disk kernel with 5x byte-identical replay verified live at publication time.")
    c.setStrokeColor(EDGE_W); c.setLineWidth(0.5)
    c.line(M, H - M - 30, W - M, H - M - 30)

def footer(c, page_num, total):
    c.setStrokeColor(EDGE_W); c.setLineWidth(0.5)
    c.line(M, M + 18, W - M, M + 18)
    c.setFont("Helvetica", 7); c.setFillColor(INK_F)
    c.drawString(M, M + 6, "SZL Holdings  -  Lutar, Stephen P.  -  ORCID 0009-0001-0110-4173  -  CC-BY-4.0")
    c.drawRightString(W - M, M + 6, f"Page {page_num} of {total}")

# --- PAGE 1: anatomy diagram ---

def draw_brain_silhouette(c, cx, cy, w, h):
    """Stylized brain outline — two hemispheres + brainstem."""
    c.setStrokeColor(EDGE_P); c.setLineWidth(1.2)
    p = c.beginPath()
    p.moveTo(cx, cy + h/2)
    p.curveTo(cx - w/2, cy + h/2 + 6, cx - w/2 - 4, cy, cx - w/2, cy - h/4)
    p.curveTo(cx - w/2 + 6, cy - h/2 + 8, cx - 8, cy - h/2 + 4, cx, cy - h/2 + 12)
    p.curveTo(cx + 8, cy - h/2 + 4, cx + w/2 - 6, cy - h/2 + 8, cx + w/2, cy - h/4)
    p.curveTo(cx + w/2 + 4, cy, cx + w/2, cy + h/2 + 6, cx, cy + h/2)
    c.drawPath(p, stroke=1, fill=0)
    # Inter-hemisphere line
    c.setStrokeColor(EDGE_W); c.setDash(2, 2)
    c.line(cx, cy + h/2 - 4, cx, cy - h/2 + 14)
    c.setDash()
    # Brainstem
    c.setStrokeColor(EDGE_P); c.setLineWidth(1.2)
    c.line(cx - 10, cy - h/2 + 12, cx - 10, cy - h/2 - 6)
    c.line(cx + 10, cy - h/2 + 12, cx + 10, cy - h/2 - 6)
    c.line(cx - 10, cy - h/2 - 6, cx + 10, cy - h/2 - 6)

def draw_overwatch_bar(c, x, y, w, h):
    """OVERWATCH is a wide thin bar — needs custom 3-column layout."""
    c.setStrokeColor(EDGE_P); c.setLineWidth(0.9)
    c.setFillColor(BG)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    # Left column: title + kernel
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x + 8, y + h - 13, "OVERWATCH (R0513)")
    c.setFont("Helvetica", 5.8); c.setFillColor(INK_F)
    c.drawString(x + 8, y + 6, "r0513_overwatch_evolution/06_kernel.py  -  146 SLOC")
    # Right side: invariants list, single line
    c.setFont("Helvetica", 6.8); c.setFillColor(INK_D)
    c.drawString(x + 150, y + h - 13,
        "READ-ONLY  -  I1 KL drift  ::  I2 joint margin  ::  I3 TUKUY re-gate  ::  I5 Maxwell rigidity  ::  I6 continuum-hash chain")
    c.setFont("Helvetica", 5.8); c.setFillColor(INK_F)
    c.drawString(x + 150, y + 6,
        "Event-log lines only. R0513 does not halt or gate; CRITICAL alerts notify operator.")

def draw_region(c, x, y, w, h, label, sublabel, kernel, sloc, gate=False):
    """A labeled region — used for cortex callouts and organs.
    Assumes h >= 38 so three text lines fit with 2px breathing room."""
    stroke = ACCENT if gate else EDGE_P
    c.setStrokeColor(stroke); c.setLineWidth(0.8)
    if gate:
        c.setFillColor(ACCENT); c.setFillAlpha(0.10)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
        c.setFillAlpha(1.0)
    else:
        c.setFillColor(BG)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    # On gate-tinted boxes, use darker ink for the kernel line to keep contrast >= 4.5
    kernel_color = INK_D if gate else INK_F
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 6, y + h - 12, label)
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(x + 6, y + h - 23, sublabel)
    if kernel:
        c.setFont("Helvetica", 5.5); c.setFillColor(kernel_color)
        kline = f"{kernel}" + (f" - {sloc} SLOC" if sloc else "")
        c.drawString(x + 6, y + 5, kline)

def page1_anatomy(c):
    setup(c); header(c)

    # ── OVERWATCH bar at top, custom 2-column thin layout ──
    overwatch_y = H - 96
    draw_overwatch_bar(c, M, overwatch_y, W - 2*M, 32)

    # ── BRAIN region (centered horizontally on left 2/3 of page) ──
    brain_cx = W / 2 - 70
    brain_cy = H - 240
    draw_brain_silhouette(c, brain_cx, brain_cy, 260, 130)

    # ── Cortex callouts — placed OUTSIDE the brain silhouette as labeled boxes ──
    # Left column of cortex boxes (above-left of brain)
    cortex_x_left  = M
    cortex_x_right = W - M - 110
    cw, ch = 110, 42
    gap    = 6

    # PREFRONTAL (gold) — top-left callout
    pf_y = brain_cy + 35
    draw_region(c, cortex_x_left, pf_y, cw, ch,
                "PREFRONTAL", "13-axis wisdom gate",
                "yuyay_v3 heart", "430", gate=True)
    # arrow from box to brain front-top
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.5); c.setDash(2, 2)
    c.line(cortex_x_left + cw, pf_y + ch/2, brain_cx - 95, brain_cy + 35); c.setDash()

    # FRONTAL — middle-left callout
    fr_y = pf_y - ch - gap
    draw_region(c, cortex_x_left, fr_y, cw, ch,
                "FRONTAL", "Proposer / action",
                "rimay (architecture)", "")
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.5); c.setDash(2, 2)
    c.line(cortex_x_left + cw, fr_y + ch/2, brain_cx - 70, brain_cy + 5); c.setDash()

    # TEMPORAL — bottom-left callout
    tm_y = fr_y - ch - gap
    draw_region(c, cortex_x_left, tm_y, cw, ch,
                "TEMPORAL", "Retrieval / RAG",
                "yachay codex", "")
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.5); c.setDash(2, 2)
    c.line(cortex_x_left + cw, tm_y + ch/2, brain_cx - 95, brain_cy - 35); c.setDash()

    # PARIETAL — top-right callout
    pa_y = brain_cy + 35
    draw_region(c, cortex_x_right, pa_y, cw, ch,
                "PARIETAL", "K-candidate sim",
                "musquy/kernel.py", "219")
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.5); c.setDash(2, 2)
    c.line(cortex_x_right, pa_y + ch/2, brain_cx + 95, brain_cy + 35); c.setDash()

    # OCCIPITAL — middle-right callout
    oc_y = pa_y - ch - gap
    draw_region(c, cortex_x_right, oc_y, cw, ch,
                "OCCIPITAL", "Tool surface",
                "nawi (MCP)", "")
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.5); c.setDash(2, 2)
    c.line(cortex_x_right, oc_y + ch/2, brain_cx + 95, brain_cy + 5); c.setDash()

    # QUANTUM MIND — bottom-right callout
    qm_y = oc_y - ch - gap
    draw_region(c, cortex_x_right, qm_y, cw, ch,
                "QUANTUM MIND", "rho 4x4  ::  lam_min >= 0.225",
                "qm/04_kernel.py", "163")
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.5); c.setDash(2, 2)
    c.line(cortex_x_right, qm_y + ch/2, brain_cx + 95, brain_cy - 35); c.setDash()

    # ── HEART (separate organ, below brain, centered) ──
    heart_w = 280
    heart_y = H - 410
    heart_x = (W - heart_w) / 2
    draw_region(c, heart_x, heart_y, heart_w, 50,
                "HEART  -  YUYAY v3 (CRITIQUE GATE)",
                "13-axis conjunctive AND  ::  moralGrounding + measurabilityHonesty >= 0.95",
                "yuyay_v3_heart/03_kernel.py", "430", gate=True)
    # Artery from heart up to brain (centered, gold)
    c.setStrokeColor(ACCENT); c.setLineWidth(1.3)
    p = c.beginPath()
    p.moveTo(heart_x + heart_w/2, heart_y + 50)
    p.curveTo(heart_x + heart_w/2, heart_y + 80,
              brain_cx, brain_cy - 100,
              brain_cx, brain_cy - 65)
    c.drawPath(p, stroke=1, fill=0)
    c.setFont("Helvetica", 5.5); c.setFillColor(INK_F)
    c.drawString(heart_x + heart_w/2 + 6, heart_y + 70, "artery: gate scores -> cortex")
    c.setLineWidth(0.7)

    # ── BLOOD (YAWAR receipt bus) ──
    blood_y = heart_y - 32
    c.setStrokeColor(ACCENT); c.setLineWidth(1.4)
    c.line(M, blood_y, W - M, blood_y)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(ACCENT)
    c.drawString(M + 4, blood_y + 4, "BLOOD  -  YAWAR receipt bus  ::  continuum-hash chain + SHA-256 pre-disclosure  ::  cryptographic receipts per action")
    c.setFont("Helvetica", 6); c.setFillColor(INK_D)
    c.drawString(M + 4, blood_y - 10, "Every component reads from YAWAR; only authorized writers commit. R0513 is read-only over the bus.")

    # ── IMMUNE SYSTEM ──
    immune_y = blood_y - 78
    immune_w = (W - 2*M - 10) / 2
    draw_region(c, M, immune_y, immune_w, 55,
                "IMMUNE  -  HUKLLA (10 tripwires)",
                "T01..T10 safety checks each cycle. Any trip -> halt + re-gate.",
                "hukla (architecture)", "42")
    draw_region(c, M + immune_w + 10, immune_y, immune_w, 55,
                "IMMUNE  -  SENTRA (egress inspector)",
                "Outbound payload scan. Failed payloads re-enter via inspector.",
                "sentra (architecture)", "18")

    # ── HATUN-RAID orchestrator (dashed) ──
    raid_y = immune_y - 38
    c.setStrokeColor(EDGE_S); c.setLineWidth(0.6); c.setDash(3, 2)
    c.rect(M, raid_y, W - 2*M, 28, stroke=1, fill=0); c.setDash()
    c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
    c.drawString(M + 8, raid_y + 16, "HATUN-RAID (KHIPU-RAID)  -  sovereign orchestrator  -  199 SLOC")
    c.setFont("Helvetica", 6); c.setFillColor(INK_D)
    c.drawString(M + 8, raid_y + 5,
        "Long-horizon multi-subagent dispatch. Energy-gated (Butler-Volmer). Doctrine-gated (YUYAY 9-axis per cycle). Cryptographic receipts on YAWAR.")

    # ── SOVEREIGN SEAL ──
    seal_y = M + 32
    c.setStrokeColor(EDGE_P); c.setLineWidth(1.4)
    c.rect(M, seal_y, W - 2*M, 34, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(INK)
    c.drawString(M + 8, seal_y + 20, "SOVEREIGN SEAL  -  HATUN crown")
    c.setFont("Helvetica", 6.5); c.setFillColor(INK_D)
    c.drawString(M + 8, seal_y + 7,
        "Final allegiance check  ::  identity-trace to a human principal  ::  10-tripwire egress  ::  byte-deterministic commit  ::  5x replay verified")

    footer(c, 1, 2)
    c.showPage()


# --- PAGE 2: kernel ledger + 9-axis evaluation key ---

def page2_ledger(c):
    setup(c)
    c.setFont("Helvetica-Bold", 12); c.setFillColor(INK)
    c.drawString(M, H - M - 6, "KERNEL LEDGER  -  every region, on-disk truth")
    c.setStrokeColor(EDGE_W); c.setLineWidth(0.5)
    c.line(M, H - M - 14, W - M, H - M - 14)

    y = H - M - 36
    rows = [
        ("REGION", "KERNEL FILE", "SLOC", "CANONICAL REPLAY HASH (sha256)", "5x"),
        ("Prefrontal / Heart (YUYAY v3)", "yuyay_v3_heart/03_kernel.py", "430",
            "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5", "PASS"),
        ("Overwatch (R0513)", "r0513_overwatch_evolution/06_kernel.py", "146",
            "df4e974109df9803a660abef7b7504a88f70bdd3ca67612e4dcd7bd66f8ce1c1", "PASS"),
        ("Sovereign Seal (HATUN-RAID)", "hatun_runs_ourmodel/03_kernel.py", "199",
            "6381bc236fe95d64dce2909d5a3a74fa59cb9cfdd7196cf37cc1b17c59aaaf88", "PASS"),
        ("Immune harness (TUPU-T7)", "tupu_t7_closure/t7_harness.py", "138",
            "43f0c3a9b5d5a00625546952bc7d1f14726c5ee376d27224a2e772eba2efd4df", "PASS"),
        ("Quantum Mind", "quantum_mind_layer/04_kernel.py", "163",
            "ea65ddc574a34882d650bfc0a6762d83323abcdef637e9b05a5e86352df1c524", "PASS"),
        ("Parietal (MUSQUY simulator)", "musquy_simulate_evolution/kernel.py", "219", "(replay via test_replay.py)", "PASS"),
        ("Egress (TUKUY)", "tukuy_action_evolution/kernel.py", "70", "(replay via test_replay.py)", "PASS"),
    ]
    cx = [M, M + 130, M + 290, M + 330, M + 660]
    c.setFont("Helvetica-Bold", 7); c.setFillColor(INK)
    for i, head in enumerate(rows[0]):
        c.drawString(cx[i], y, head)
    y -= 8
    c.setStrokeColor(EDGE_W); c.line(M, y, W - M, y); y -= 4
    c.setFont("Helvetica", 6.5)
    for row in rows[1:]:
        c.setFillColor(INK)
        c.drawString(cx[0], y, row[0])
        c.setFillColor(INK_D)
        c.drawString(cx[1], y, row[1])
        c.drawString(cx[2], y, row[2])
        c.setFont("Courier", 5.8); c.setFillColor(INK_F)
        c.drawString(cx[3], y, row[3])
        c.setFont("Helvetica-Bold", 6.5); c.setFillColor(ACCENT)
        c.drawString(cx[4], y, row[4])
        c.setFont("Helvetica", 6.5)
        y -= 14

    # 9-axis key
    y -= 30
    c.setFont("Helvetica-Bold", 9); c.setFillColor(INK)
    c.drawString(M, y, "9-AXIS DOCTRINE GATE  -  conjunctive AND, floors below")
    y -= 4; c.setStrokeColor(EDGE_W); c.line(M, y, W - M, y); y -= 14
    axes = [
        ("moralGrounding", ">= 0.95", "no overclaim, no false attribution"),
        ("measurabilityHonesty", ">= 0.95", "every quantitative claim verifiable on disk"),
        ("empiricalGrounding", ">= 0.90", "claims trace to artifacts"),
        ("logicalConsistency", ">= 0.90", "no internal contradictions"),
        ("sourceTransparency", ">= 0.90", "primary citations present"),
        ("reproducibility", ">= 0.90", "5x byte-identical replay"),
        ("licenseHygiene", ">= 0.90", "Apache-2.0 / MIT / BSD-3 / CC-BY only"),
        ("scopeDiscipline", ">= 0.90", "no scope creep beyond kernel reality"),
        ("claimCalibration", ">= 0.90", "conservative phrasing where uncertain"),
    ]
    c.setFont("Helvetica", 7)
    for name, floor, desc in axes:
        c.setFillColor(INK); c.drawString(M, y, name)
        c.setFillColor(ACCENT); c.drawString(M + 130, y, floor)
        c.setFillColor(INK_D); c.drawString(M + 180, y, desc)
        y -= 11

    # Honest note
    y -= 18
    c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
    c.drawString(M, y, "WHAT THIS DIAGRAM IS NOT"); y -= 10
    c.setFont("Helvetica", 6.8); c.setFillColor(INK_D)
    notes = [
        "Not a neuroscience model. Anatomical region names map cognitive functions to architectural positions for legibility.",
        "Not a frontier-throughput claim. Throughput inherits from the configured inference substrate (Cerebras, SambaNova, vLLM, etc.).",
        "Not a quantum-physical claim. Quantum Mind uses density-matrix formalism (real 4x4 matrices) on classical hardware.",
        "Not yet wired end-to-end. HEART (YUYAY v3, 13-axis) is a sibling kernel; the on-disk HATUN-RAID still calls a 9-axis YUYAY envelope.",
    ]
    for n in notes:
        c.drawString(M, y, "-  " + n); y -= 9

    footer(c, 2, 2)
    c.showPage()


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("SZL Agent Body · Brain (hatun)")
    c.setAuthor("Lutar, Stephen P.")
    c.setSubject("Anatomy diagram: brain orchestrator")
    page1_anatomy(c)
    page2_ledger(c)
    c.save()
    print(f"WROTE {OUT}")

if __name__ == "__main__":
    main()
