from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _clean(text: str) -> str:
    text = text or ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", text)
    return text


def _svg_to_png_bytes(diagram_svg: str, width: int = 900) -> bytes | None:
    """Rasterize SVG for DOCX (and PDF fallback)."""
    if not diagram_svg or "<svg" not in diagram_svg:
        return None
    svg = diagram_svg.strip()
    if not svg.startswith("<?xml"):
        svg = '<?xml version="1.0" encoding="UTF-8"?>\n' + svg
    try:
        import cairosvg  # type: ignore

        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width)
    except Exception:
        pass
    try:
        from reportlab.graphics import renderPM
        from svglib.svglib import svg2rlg

        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "d.svg"
            png_path = Path(tmp) / "d.png"
            svg_path.write_text(svg, encoding="utf-8")
            drawing = svg2rlg(str(svg_path))
            if drawing is None:
                return None
            renderPM.drawToFile(drawing, str(png_path), fmt="PNG")
            return png_path.read_bytes()
    except Exception:
        return None


def _svg_flowable(diagram_svg: str, max_width: float = 160 * mm):
    """Embed diagram as PNG Image (reliable across ReportLab backends)."""
    png = _svg_to_png_bytes(diagram_svg)
    if not png:
        return None
    bio = io.BytesIO(png)
    img = RLImage(bio)
    # Preserve aspect from a typical template (~640x360)
    img.drawWidth = max_width
    img.drawHeight = max_width * (360 / 640)
    return img

def build_solution_pdf(
    *,
    title: str,
    question: str,
    explanation: str,
    answers: list[dict[str, Any]],
    diagram_svg: str | None = None,
    subject: str | None = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"CivilMaster — {title}",
        author="CivilMaster",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "CMTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    h2 = ParagraphStyle(
        "CMH2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#1d4e89"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "CMBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
    )
    muted = ParagraphStyle(
        "CMMuted",
        parent=body,
        textColor=colors.HexColor("#64748b"),
        fontSize=9,
    )

    story: list[Any] = []
    story.append(Paragraph("CivilMaster", h1))
    story.append(Paragraph("B.Tech Civil · worked solution", muted))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 8))
    story.append(Paragraph(_clean(title), h2))
    if subject:
        story.append(Paragraph(_clean(f"Subject: {subject}"), muted))

    story.append(Paragraph("Question", h2))
    for para in (question or "").split("\n"):
        if para.strip():
            story.append(Paragraph(_clean(para), body))
            story.append(Spacer(1, 2))

    story.append(Paragraph("Solution", h2))
    for line in (explanation or "No written steps available.").split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        if line.startswith("##"):
            story.append(Paragraph(_clean(line.lstrip("# ").strip()), h2))
        elif line.startswith("- ") or line.startswith("* "):
            story.append(Paragraph("• " + _clean(line[2:]), body))
        else:
            story.append(Paragraph(_clean(line), body))
            story.append(Spacer(1, 2))

    if answers:
        story.append(Paragraph("Final answers", h2))
        rows = [["Quantity", "Value", "Unit"]]
        for a in answers:
            rows.append(
                [
                    str(a.get("label") or ""),
                    str(a.get("value") or ""),
                    str(a.get("unit") or ""),
                ]
            )
        table = Table(rows, colWidths=[90 * mm, 40 * mm, 30 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)

    if diagram_svg:
        story.append(Paragraph("Diagram", h2))
        flow = _svg_flowable(diagram_svg)
        if flow is not None:
            story.append(KeepTogether([flow]))
        else:
            story.append(
                Paragraph(
                    "Diagram could not be embedded; open the web solution or download the DXF.",
                    muted,
                )
            )

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "Generated by CivilMaster. Always cross-check with IS codes and faculty guidance.",
            muted,
        )
    )
    doc.build(story)
    return buffer.getvalue()


def build_solution_docx(
    *,
    title: str,
    question: str,
    explanation: str,
    answers: list[dict[str, Any]],
    subject: str | None = None,
    diagram_svg: str | None = None,
) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    heading = doc.add_heading("CivilMaster", level=0)
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    sub = doc.add_paragraph("B.Tech Civil · worked solution")
    for run in sub.runs:
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    doc.add_heading(title or "Assignment", level=1)
    if subject:
        doc.add_paragraph(f"Subject: {subject}")

    doc.add_heading("Question", level=2)
    doc.add_paragraph(question or "")

    doc.add_heading("Solution", level=2)
    for line in (explanation or "No written steps available.").split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("##"):
            doc.add_heading(line.lstrip("# ").strip(), level=3)
        else:
            doc.add_paragraph(line)

    if answers:
        doc.add_heading("Final answers", level=2)
        table = doc.add_table(rows=1, cols=3)
        hdr = table.rows[0].cells
        hdr[0].text = "Quantity"
        hdr[1].text = "Value"
        hdr[2].text = "Unit"
        for a in answers:
            row = table.add_row().cells
            row[0].text = str(a.get("label") or "")
            row[1].text = str(a.get("value") or "")
            row[2].text = str(a.get("unit") or "")

    if diagram_svg:
        doc.add_heading("Diagram", level=2)
        png = _svg_to_png_bytes(diagram_svg)
        if png:
            doc.add_picture(io.BytesIO(png), width=Inches(5.8))
        else:
            doc.add_paragraph("Diagram available in the web app / DXF download.")

    doc.add_paragraph("")
    note = doc.add_paragraph(
        "Generated by CivilMaster. Always cross-check with IS codes and faculty guidance."
    )
    for run in note.runs:
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def build_beam_dxf(variables: dict[str, Any] | None = None) -> bytes:
    """Simply supported beam with UDL hatch — AutoCAD R2010 DXF."""
    import ezdxf

    variables = variables or {}
    length = float(variables.get("L") or variables.get("span") or 4000.0)
    scale = 200.0 / max(length, 1.0)
    L = length * scale

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (L, 0))
    msp.add_line((0, 0), (-5, -12))
    msp.add_line((0, 0), (5, -12))
    msp.add_line((L, 0), (L - 5, -12))
    msp.add_line((L, 0), (L + 5, -12))
    msp.add_line((0, 25), (L, 25))
    step = max(10, int(L // 20) or 10)
    for i in range(0, int(L) + 1, step):
        msp.add_line((i, 25), (i, 12))
    t1 = msp.add_text("Simply supported beam (CivilMaster)", dxfattribs={"height": 8})
    t1.dxf.insert = (0, 40)
    t2 = msp.add_text(f"L = {length}", dxfattribs={"height": 5})
    t2.dxf.insert = (0, -28)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "beam.dxf"
        doc.saveas(path)
        return path.read_bytes()


def build_section_dxf(variables: dict[str, Any] | None = None) -> bytes:
    """Rectangular cross-section outline for AutoCAD."""
    import ezdxf

    variables = variables or {}
    b = float(variables.get("b") or 200.0)
    d = float(variables.get("d") or 300.0)
    scale = 120.0 / max(b, d, 1.0)
    W, H = b * scale, d * scale

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H), (0, 0)], close=True)
    # centroid mark
    cx, cy = W / 2, H / 2
    msp.add_line((cx - 6, cy), (cx + 6, cy))
    msp.add_line((cx, cy - 6), (cx, cy + 6))
    t = msp.add_text(f"Section b={b} d={d} (CivilMaster)", dxfattribs={"height": 6})
    t.dxf.insert = (0, H + 12)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "section.dxf"
        doc.saveas(path)
        return path.read_bytes()


def build_rcc_section_dxf(variables: dict[str, Any] | None = None) -> bytes:
    """Singly reinforced rectangular RCC section sketch."""
    import ezdxf

    variables = variables or {}
    b = float(variables.get("b") or 230.0)
    d = float(variables.get("d") or 450.0)
    scale = 140.0 / max(b, d, 1.0)
    W, H = b * scale, d * scale

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H), (0, 0)], close=True)
    # tension steel row near bottom
    y_bar = 12
    for x in (W * 0.25, W * 0.5, W * 0.75):
        msp.add_circle((x, y_bar), 4)
    t = msp.add_text("RCC section (CivilMaster)", dxfattribs={"height": 6})
    t.dxf.insert = (0, H + 12)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rcc.dxf"
        doc.saveas(path)
        return path.read_bytes()


def build_solution_dxf(
    *,
    diagram_type: str | None = None,
    variables: dict[str, Any] | None = None,
) -> bytes:
    """Pick the best CAD sketch for the solved problem type."""
    dtype = (diagram_type or "").lower()
    if dtype in ("section", "rect_section"):
        return build_section_dxf(variables)
    if dtype in ("rcc_section", "rcc"):
        return build_rcc_section_dxf(variables)
    # Default / beam_sfd_bmd
    return build_beam_dxf(variables)
