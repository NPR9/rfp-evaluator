"""Generate the four synthetic supplier RFP responses + error-case files.

    python scripts/generate_sample_pdfs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from supplier_content import BUYER, REQUIREMENT_SUMMARY, RFP_TITLE, SUPPLIERS  # noqa: E402

OUT = ROOT / "sample_data" / "pdfs"
ERR = ROOT / "sample_data" / "error_cases"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=20, leading=24, alignment=TA_LEFT,
                    spaceAfter=2)
TAG = ParagraphStyle("TAG", parent=ss["Normal"], fontSize=10, textColor=colors.HexColor("#555555"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, leading=16, spaceBefore=10,
                    spaceAfter=4, textColor=colors.HexColor("#1F3A5F"))
BODY = ParagraphStyle("BODY", parent=ss["BodyText"], fontSize=10, leading=14.5, spaceAfter=6)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8, textColor=colors.HexColor("#777777"))
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=9, leading=12, spaceAfter=0)


def _table(rows, widths=None):
    data = [[Paragraph(str(c), CELL) for c in r] for r in rows]
    widths = widths or {2: [110 * mm, 60 * mm], 3: [55 * mm, 20 * mm, 95 * mm]}.get(len(rows[0]))
    t = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA8B8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _footer(name):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(20 * mm, 12 * mm, f"{name} - Response to {BUYER} RFP-2026-017 - "
                                            "FICTIONAL DOCUMENT FOR CLASSROOM USE")
        canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def build_proposal(s: dict) -> Path:
    path = OUT / s["file"]
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title=f"{s['name']} - RFP-2026-017 Proposal", author=s["name"])
    story = [
        Paragraph(s["name"], H1),
        Paragraph(s["tagline"], TAG),
        Spacer(1, 6),
        _table([["Proposal to", BUYER], ["Request", RFP_TITLE],
                ["Supplier", s["name"]], ["Submission date", s["date"]],
                ["Validity", "90 days from submission"]], widths=[40 * mm, 130 * mm]),
        Spacer(1, 6),
        Paragraph("<b>Our understanding of the requirement.</b> " + REQUIREMENT_SUMMARY, BODY),
    ]
    for heading, content in s["sections"]:
        if heading.startswith("TABLE:"):
            story += [_table(content), Spacer(1, 6)]
            continue
        if heading:
            story.append(Paragraph(heading, H2))
        story += [Paragraph(p, BODY) for p in content]
    story += [Spacer(1, 10),
              Paragraph("All organisations, people, clients and figures in this document are "
                        "fictional and were created for an academic exercise.", SMALL)]
    doc.build(story, onFirstPage=_footer(s["name"]), onLaterPages=_footer(s["name"]))
    return path


def build_error_cases() -> None:
    ERR.mkdir(parents=True, exist_ok=True)
    # 1) A PDF with no extractable text (like a scanned document without OCR).
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(ERR / "Scanned_No_Text_Proposal.pdf"), pagesize=A4)
    c.setFillColor(colors.HexColor("#DDDDDD"))
    c.rect(30 * mm, 60 * mm, 150 * mm, 180 * mm, fill=1, stroke=0)   # a "scanned image"
    c.showPage()
    c.save()
    # 2) A file that has a .pdf extension but is not a PDF.
    (ERR / "Corrupt_Not_A_PDF.pdf").write_text("This is a plain text file renamed to .pdf\n")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for s in SUPPLIERS:
        p = build_proposal(s)
        from pypdf import PdfReader
        print(f"{p.name}: {len(PdfReader(str(p)).pages)} pages")
    build_error_cases()
    print("Error-case files written to", ERR)
