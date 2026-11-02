import argparse
import re
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_DIR / "reports" / "PROJECT_REPORT.md"
DEFAULT_OUTPUT = PROJECT_DIR.parent / "FloodNet_Davao_ML_Project_Report.docx"
NAVY = "16324F"
TEAL = "087E8B"
LIGHT_BLUE = "EAF2F8"
PALE = "F4F7FA"
DARK = "253746"
METRICS = {
    "5-year": {"Precision": 0.724, "Recall": 0.591, "F1": 0.651, "ROC-AUC": 0.822},
    "25-year": {"Precision": 0.821, "Recall": 0.625, "F1": 0.710, "ROC-AUC": 0.851},
    "100-year": {"Precision": 0.816, "Recall": 0.857, "F1": 0.836, "ROC-AUC": 0.775},
}
COLORS = {
    "Precision": "087E8B",
    "Recall": "F4A261",
    "F1": "547AA5",
    "ROC-AUC": "7566A8",
}


def shade_cell(cell, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def set_repeat_table_header(row) -> None:
    properties = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    properties.append(repeat)


def set_cell_margins(cell, top=70, start=80, bottom=70, end=80) -> None:
    properties = cell._tc.get_or_add_tcPr()
    margins = properties.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        properties.append(margins)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        element = margins.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            margins.append(element)
        element.set(qn("w:w"), str(value))
        element.set(qn("w:type"), "dxa")


def add_hyperlink(paragraph, label: str, url: str) -> None:
    relationship = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), TEAL)
    properties.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    run.append(properties)
    text = OxmlElement("w:t")
    text.text = label
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_inline(paragraph, text: str, base_size: float = 10.0) -> None:
    token_pattern = re.compile(
        r"\[([^\]]+)\]\((https?://[^)]+)\)|(\*\*[^*]+\*\*)|(`[^`]+`)|(\*[^*]+\*)"
    )
    position = 0
    for match in token_pattern.finditer(text):
        if match.start() > position:
            paragraph.add_run(text[position : match.start()])
        label, url, bold, code, italic = match.groups()
        if label is not None:
            add_hyperlink(paragraph, label, url)
        elif bold is not None:
            run = paragraph.add_run(bold[2:-2])
            run.bold = True
        elif code is not None:
            run = paragraph.add_run(code[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(base_size - 0.4)
            run.font.color.rgb = RGBColor.from_string(NAVY)
        elif italic is not None:
            run = paragraph.add_run(italic[1:-1])
            run.italic = True
        position = match.end()
    if position < len(text):
        paragraph.add_run(text[position:])


def parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def add_markdown_table(document, lines: list[str]) -> None:
    rows = [parse_table_row(line) for line in lines]
    if len(rows) > 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        rows.pop(1)
    if not rows:
        return

    column_count = max(map(len, rows))
    table = document.add_table(rows=0, cols=column_count)
    table.style = "Table Grid"
    table.autofit = True
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for column_index, cell in enumerate(cells):
            value = values[column_index] if column_index < len(values) else ""
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            for run in paragraph.runs:
                run.font.size = Pt(7.5 if column_count >= 7 else 8.5)
            add_inline(paragraph, value, base_size=8.5)
            for run in paragraph.runs:
                run.font.size = Pt(7.5 if column_count >= 7 else 8.5)
                if row_index == 0:
                    run.bold = True
                    run.font.color.rgb = RGBColor(255, 255, 255)
            shade_cell(cell, NAVY if row_index == 0 else (PALE if row_index % 2 == 0 else "FFFFFF"))
        if row_index == 0:
            set_repeat_table_header(table.rows[0])
    document.add_paragraph().paragraph_format.space_after = Pt(1)


def get_chart_font(size: int):
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for font_path in candidates:
        if font_path.is_file():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def make_metric_chart() -> BytesIO:
    width, height = 1200, 620
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_chart_font(27)
    label_font = get_chart_font(18)
    small_font = get_chart_font(15)

    plot_left, plot_right = 95, 1160
    plot_top, plot_bottom = 80, 455
    draw.text((plot_left, 20), "Spatial-holdout metrics: Random Forest", fill=f"#{NAVY}", font=title_font)
    for tick in range(0, 11, 2):
        value = tick / 10
        y = plot_bottom - value * (plot_bottom - plot_top)
        draw.line((plot_left, y, plot_right, y), fill="#D9E2EA", width=1)
        draw.text((45, y - 10), f"{value:.1f}", fill=f"#{DARK}", font=small_font)

    scenario_centers = [275, 625, 975]
    metric_names = ["Precision", "Recall", "F1", "ROC-AUC"]
    bar_width, gap = 42, 12
    group_width = len(metric_names) * bar_width + (len(metric_names) - 1) * gap
    for center, (scenario, values) in zip(scenario_centers, METRICS.items()):
        group_left = center - group_width // 2
        for metric_index, metric in enumerate(metric_names):
            x1 = group_left + metric_index * (bar_width + gap)
            x2 = x1 + bar_width
            y2 = plot_bottom - values[metric] * (plot_bottom - plot_top)
            draw.rounded_rectangle((x1, y2, x2, plot_bottom), radius=5, fill=f"#{COLORS[metric]}")
            draw.text((x1 - 4, y2 - 25), f"{values[metric]:.2f}", fill=f"#{DARK}", font=small_font)
        draw.text((center - 58, plot_bottom + 20), scenario, fill=f"#{NAVY}", font=label_font)

    legend_y = 535
    legend_x = [145, 390, 620, 800]
    for x, metric in zip(legend_x, metric_names):
        draw.rounded_rectangle((x, legend_y, x + 24, legend_y + 18), radius=4, fill=f"#{COLORS[metric]}")
        draw.text((x + 33, legend_y - 3), metric, fill=f"#{DARK}", font=small_font)
    draw.text((95, 490), "Metric score", fill=f"#{DARK}", font=small_font)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run("Page ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)


def configure_document(document) -> None:
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.72)
    section.right_margin = Inches(0.72)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.35)

    normal = document.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor.from_string(DARK)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1

    for style_name, size, color in (
        ("Heading 1", 16, NAVY),
        ("Heading 2", 13, TEAL),
        ("Heading 3", 11, NAVY),
    ):
        style = document.styles[style_name]
        style.font.name = "Aptos Display"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(10)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header.add_run("FLOODNET DAVAO  |  MACHINE LEARNING PROJECT")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(TEAL)
    add_page_number(section.footer.paragraphs[0])


def add_cover(document) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(45)
    paragraph.paragraph_format.space_after = Pt(12)
    run = paragraph.add_run("Name:  _________________________________________________")
    run.bold = True
    run.font.size = Pt(12)

    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(36)
    run = paragraph.add_run("Course & Year:  __________________________________________")
    run.bold = True
    run.font.size = Pt(12)

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("Title:")
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor.from_string(TEAL)

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(5)
    paragraph.paragraph_format.space_after = Pt(20)
    run = paragraph.add_run(
        "Machine Learning Classification of Road Flood-Hazard Exposure in Metro Davao"
    )
    run.bold = True
    run.font.name = "Aptos Display"
    run.font.size = Pt(24)
    run.font.color.rgb = RGBColor.from_string(NAVY)

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_inline(
        paragraph,
        "Interactive project map: [FloodNet Davao](https://floodnet-davao.onrender.com)",
    )

    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(25)
    paragraph.paragraph_format.left_indent = Inches(0.3)
    paragraph.paragraph_format.right_indent = Inches(0.3)
    paragraph.paragraph_format.space_after = Pt(10)
    paragraph.paragraph_format.keep_together = True
    shade = OxmlElement("w:shd")
    shade.set(qn("w:fill"), LIGHT_BLUE)
    paragraph._p.get_or_add_pPr().append(shade)
    run = paragraph.add_run(
        "Scope: This study classifies road exposure to supplied flood-hazard map "
        "scenarios. It does not predict when flooding will occur or estimate a "
        "calibrated real-world flood probability."
    )
    run.italic = True
    run.font.size = Pt(10)
    document.add_page_break()


def markdown_lines_to_docx(document, lines: list[str]) -> None:
    in_report = False
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if stripped == "## 1. Introduction":
            in_report = True
        if not in_report:
            index += 1
            continue
        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Inches(0.2)
            paragraph.paragraph_format.right_indent = Inches(0.1)
            paragraph.paragraph_format.space_after = Pt(8)
            properties = paragraph._p.get_or_add_pPr()
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), PALE)
            properties.append(shading)
            run = paragraph.add_run("\n".join(code_lines))
            run.font.name = "Consolas"
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor.from_string(NAVY)
            index += 1
            continue

        if stripped.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            add_markdown_table(document, table_lines)
            continue

        heading = re.match(r"^(#{2,4})\s+(.+)$", stripped)
        if heading:
            level = min(len(heading.group(1)) - 1, 3)
            document.add_heading(heading.group(2), level=level)
            index += 1
            if heading.group(2).startswith("5.1 Spatial-holdout results"):
                chart_paragraph = document.add_paragraph()
                chart_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                chart_paragraph.add_run().add_picture(
                    make_metric_chart(),
                    width=Inches(6.7),
                )
                caption = document.add_paragraph(
                    "Figure 1. Random Forest precision, recall, F1, and ROC-AUC "
                    "on the 5 km spatial holdout. The chart excludes the "
                    "majority-class baseline; see the results table."
                )
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in caption.runs:
                    run.italic = True
                    run.font.size = Pt(8)
                    run.font.color.rgb = RGBColor.from_string("52636F")
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[index].strip()))
                index += 1
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Inches(0.25)
            paragraph.paragraph_format.right_indent = Inches(0.15)
            paragraph.paragraph_format.space_after = Pt(8)
            properties = paragraph._p.get_or_add_pPr()
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), LIGHT_BLUE)
            properties.append(shading)
            add_inline(paragraph, " ".join(quote_lines))
            continue

        list_match = re.match(r"^\s*(?:[-*]\s+|\d+\.\s+)(.*)$", raw_line)
        if list_match:
            ordered = bool(re.match(r"^\s*\d+\.\s+", raw_line))
            paragraph = document.add_paragraph(
                style="List Number" if ordered else "List Bullet"
            )
            add_inline(paragraph, list_match.group(1))
            index += 1
            while index < len(lines) and lines[index].startswith(("  ", "    ")):
                continuation = lines[index].strip()
                if continuation and not continuation.startswith(("-", "*")):
                    paragraph.add_run(" ")
                    add_inline(paragraph, continuation)
                    index += 1
                else:
                    break
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            following = lines[index]
            next_stripped = following.strip()
            if (
                not next_stripped
                or next_stripped.startswith(("|", "```", ">"))
                or re.match(r"^#{2,4}\s+", next_stripped)
                or re.match(r"^\s*(?:[-*]\s+|\d+\.\s+)", following)
            ):
                break
            paragraph_lines.append(next_stripped)
            index += 1
        paragraph = document.add_paragraph()
        add_inline(paragraph, " ".join(paragraph_lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the project report to DOCX.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Report source not found: {SOURCE}")

    document = Document()
    configure_document(document)
    document.core_properties.title = (
        "Machine Learning Classification of Road Flood-Hazard Exposure in Metro Davao"
    )
    document.core_properties.subject = (
        "Supervised classification of scenario-map road exposure with spatial holdout evaluation"
    )
    document.core_properties.keywords = (
        "Davao, flood exposure, machine learning, Random Forest, spatial validation"
    )

    add_cover(document)
    markdown_lines_to_docx(document, SOURCE.read_text(encoding="utf-8").splitlines())

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    verified = Document(output)
    if len(verified.tables) < 6 or not any(
        "8. Appendix A" in paragraph.text for paragraph in verified.paragraphs
    ):
        raise RuntimeError("The exported DOCX is missing expected report sections or tables.")
    print(f"Saved and verified {output}")
    print(
        f"Paragraphs: {len(verified.paragraphs)} | Tables: {len(verified.tables)} | "
        f"Size: {output.stat().st_size:,} bytes"
    )


if __name__ == "__main__":
    main()
