"""Markdown text → PDF conversion."""

import tempfile

from fpdf import FPDF

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _safe_multi_cell(pdf: FPDF, h: float, text: str) -> None:
    """Write multi_cell with X reset to left margin to avoid width errors."""
    pdf.set_x(pdf.l_margin)
    w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(w, h, text)


def text_to_pdf(text: str) -> str:
    """Convert plain/markdown text to PDF, return temp file path."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Unicode fonts for Russian text
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.add_font("DejaVu", "B", FONT_BOLD_PATH, uni=True)
    pdf.add_font("DejaVuMono", "", FONT_MONO_PATH, uni=True)

    pdf.set_font("DejaVu", size=11)

    for line in text.split("\n"):
        # Empty lines
        if not line.strip():
            pdf.ln(4)
            continue
        # Headers
        if line.startswith("### "):
            pdf.set_font("DejaVu", "B", 12)
            _safe_multi_cell(pdf, 6, line[4:])
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.set_font("DejaVu", "B", 13)
            _safe_multi_cell(pdf, 7, line[3:])
            pdf.ln(2)
        elif line.startswith("# "):
            pdf.set_font("DejaVu", "B", 15)
            _safe_multi_cell(pdf, 8, line[2:])
            pdf.ln(3)
        # Code block markers
        elif line.startswith("```"):
            continue
        # Bullet points
        elif line.startswith("- ") or line.startswith("* "):
            pdf.set_font("DejaVu", size=11)
            _safe_multi_cell(pdf, 6, "  \u2022 " + line[2:])
        else:
            pdf.set_font("DejaVu", size=11)
            _safe_multi_cell(pdf, 6, line)

    path = tempfile.mktemp(suffix=".pdf")
    pdf.output(path)
    return path
