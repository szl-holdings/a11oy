#!/usr/bin/env python3
"""
build_explainer_pdfs.py — convert new markdown explainers to PDF
(skeleton + blood_immune) using reportlab.
License: Apache-2.0 (code)
"""
import re
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

BG     = HexColor("#F5F1E8")
INK    = HexColor("#1A1A1A")
INK_D  = HexColor("#4A4A4A")
INK_F  = HexColor("#8A8A8A")
ACCENT = HexColor("#B08940")
EDGE_W = HexColor("#B0B0B0")

W, H = letter
M = 0.6 * inch
LINE_H_BODY = 13
LINE_H_CODE = 11
MAX_CHARS_BODY = 90
MAX_CHARS_CODE = 80
BASE_DIR = "/home/user/workspace/evolution_pod/finish/anatomy/explainers/linkedin"


def build_pdf(md_path, pdf_path):
    with open(md_path) as f:
        raw = f.read()

    lines = raw.split("\n")
    c = canvas.Canvas(pdf_path, pagesize=letter)

    def new_page():
        c.setFillColor(BG)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setStrokeColor(EDGE_W)
        c.setLineWidth(0.5)
        c.line(M, M + 18, W - M, M + 18)
        c.setFont("Helvetica", 7)
        c.setFillColor(INK_F)
        c.drawString(M, M + 6, "Lutar, Stephen P. — SZL Holdings  ·  ORCID 0009-0001-0110-4173  ·  CC-BY-4.0")
        c.drawRightString(W - M, M + 6, "© SZL Holdings · CC-BY-4.0")
        return H - M - 14

    def wrap_text(text, max_chars):
        words = text.split()
        lines_out = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if len(test) > max_chars:
                if cur:
                    lines_out.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines_out.append(cur)
        return lines_out if lines_out else [""]

    y = new_page()
    in_code = False
    code_buf = []

    for raw_line in lines:
        # Handle code fences
        if raw_line.startswith("```"):
            if in_code:
                # Flush code block
                for cl in code_buf:
                    if y < M + 40:
                        c.showPage()
                        y = new_page()
                    c.setFont("Courier", 7)
                    c.setFillColor(INK_D)
                    c.drawString(M + 12, y, cl[:MAX_CHARS_CODE])
                    y -= LINE_H_CODE
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_buf.append(raw_line)
            continue

        line = raw_line.rstrip()

        if not line:
            y -= 6
            continue

        # H1
        if line.startswith("# "):
            text = line[2:]
            if y < M + 60:
                c.showPage()
                y = new_page()
            c.setFont("Helvetica-Bold", 13)
            c.setFillColor(INK)
            c.drawString(M, y, text[:70])
            y -= 20
            c.setStrokeColor(EDGE_W)
            c.setLineWidth(0.5)
            c.line(M, y + 4, W - M, y + 4)
            y -= 8
            continue

        # H2 / H3
        if line.startswith("## ") or line.startswith("### "):
            text = line.lstrip("# ")
            if y < M + 40:
                c.showPage()
                y = new_page()
            c.setFont("Helvetica-Bold", 9.5)
            c.setFillColor(ACCENT)
            c.drawString(M, y, text[:80])
            y -= 14
            continue

        # HR ---
        if line.startswith("---"):
            c.setStrokeColor(EDGE_W)
            c.setLineWidth(0.4)
            c.line(M, y + 4, W - M, y + 4)
            y -= 10
            continue

        # Italic/bold markers → strip
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        text = re.sub(r'\*(.+?)\*',     r'\1', text)
        text = re.sub(r'`(.+?)`',       r'\1', text)

        # Bullet
        is_bullet = text.startswith("- ") or text.startswith("* ")
        if is_bullet:
            text = text[2:]
            prefix = "• "
            max_c = MAX_CHARS_BODY - 4
        else:
            prefix = ""
            max_c = MAX_CHARS_BODY

        wrapped = wrap_text(text, max_c)
        first = True
        for wl in wrapped:
            if y < M + 40:
                c.showPage()
                y = new_page()
            c.setFont("Helvetica", 8)
            c.setFillColor(INK_D)
            indent = M + (16 if is_bullet and not first else 0)
            c.drawString(M, y, (prefix if first else "  ") + wl)
            y -= LINE_H_BODY
            first = False

    c.save()
    print(f"PDF → {pdf_path}")


def main():
    build_pdf(
        f"{BASE_DIR}/linkedin_skeleton.md",
        f"{BASE_DIR}/linkedin_skeleton.pdf"
    )
    build_pdf(
        f"{BASE_DIR}/linkedin_blood_immune.md",
        f"{BASE_DIR}/linkedin_blood_immune.pdf"
    )


if __name__ == "__main__":
    main()
