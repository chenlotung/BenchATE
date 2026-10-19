"""Render staged release Markdown to readable, linked PDFs; leave source files alone."""
from html import escape
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from markdown_it import MarkdownIt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle


def register_fonts(font_dir=None):
    fonts = Path(font_dir or Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts")
    for name, filename in (("BenchCJK", "msjh.ttc"), ("BenchCJKBold", "msjhbd.ttc"),
                           ("BenchMono", "consola.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            path = fonts/filename
            if not path.is_file():
                raise FileNotFoundError(f"PDF build requires Windows font: {path}")
            pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
    pdfmetrics.registerFontFamily("BenchCJK", normal="BenchCJK", bold="BenchCJKBold",
                                 italic="BenchCJK", boldItalic="BenchCJKBold")


def release_text(text):
    # Both hyperlink targets and prose filenames should match the release layout.
    # Rename filenames, not a sentence discussing the literal `.md` extension.
    text = re.sub(r"(?<=[\w/-])\.md(?=[#)`\s.,;:]|$)", ".pdf", text, flags=re.IGNORECASE)
    text = text.replace("NI_VISA_INSTALLATION_zh-TW.txt", "NI_VISA_INSTALLATION_zh-TW.pdf")
    text = text.replace("README_PORTABLE.txt", "README_PORTABLE.pdf")
    for character in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(character, "-")
    return text


def link_target(target):
    parts = urlsplit(target)
    if parts.scheme and parts.scheme.lower() not in ("https", "http", "mailto"):
        return None
    path = re.sub(r"\.md$", ".pdf", unquote(parts.path), flags=re.IGNORECASE)
    return urlunsplit((parts.scheme, parts.netloc, quote(path, safe="/:@"), parts.query, parts.fragment))


def inline_markup(tokens):
    result, links = [], []
    for token in tokens or []:
        if token.type == "text":
            result.append(escape(token.content))
        elif token.type in ("softbreak", "hardbreak"):
            result.append("<br/>" if token.type == "hardbreak" else " ")
        elif token.type == "code_inline":
            result.append(f'<font color="#16465e">{escape(token.content)}</font>')
        elif token.type in ("strong_open", "strong_close", "em_open", "em_close", "s_open", "s_close"):
            tag = {"strong": "b", "em": "i", "s": "strike"}[token.type.rsplit("_", 1)[0]]
            result.append(f"<{('/' if token.type.endswith('close') else '')}{tag}>")
        elif token.type == "link_open":
            target = link_target(token.attrGet("href") or "")
            links.append(bool(target))
            if target:
                result.append(f'<link href="{escape(target, quote=True)}" color="#17627d">')
        elif token.type == "link_close":
            if links and links.pop():
                result.append("</link>")
        elif token.type == "image":
            # Current release docs have no embedded Markdown images. Never discard one silently.
            raise ValueError("Markdown image needs an explicit PDF layout before release")
        else:
            result.append(escape(token.content))
    return "".join(result)


class DocumentTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        level = getattr(flowable, "heading_level", None)
        if level is not None:
            level = min(level, getattr(self, "outline_level", -1) + 1)
            key = f"heading-{self.seq.nextf('heading')}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level, closed=False)
            self.outline_level = level


def styles():
    body = ParagraphStyle("Body", fontName="BenchCJK", fontSize=10, leading=16,
                          textColor=colors.HexColor("#233342"), spaceAfter=8,
                          wordWrap="CJK", alignment=TA_LEFT, splitLongWords=True)
    return {
        "body": body,
        "h1": ParagraphStyle("Title", parent=body, fontName="BenchCJKBold", fontSize=22,
                              leading=29, spaceAfter=17, keepWithNext=True),
        "h2": ParagraphStyle("Section", parent=body, fontName="BenchCJKBold", fontSize=14,
                              leading=21, spaceBefore=14, spaceAfter=8, keepWithNext=True),
        "h3": ParagraphStyle("Subsection", parent=body, fontName="BenchCJKBold", fontSize=11,
                              leading=17, spaceBefore=10, keepWithNext=True),
        "cell": ParagraphStyle("Cell", parent=body, fontSize=8.6, leading=12, spaceAfter=0),
        "head": ParagraphStyle("TableHeader", parent=body, fontName="BenchCJKBold", fontSize=8.6,
                                leading=12, textColor=colors.white, spaceAfter=0),
        "code": ParagraphStyle("Code", parent=body, fontName="BenchMono", fontSize=8.5, leading=13,
                                backColor=colors.HexColor("#f0f4f7"), borderPadding=9,
                                spaceBefore=6, spaceAfter=13),
    }


def make_table(tokens, start, width, style):
    rows, cells, headers, index = [], [], [], start + 1
    while index < len(tokens) and tokens[index].type != "table_close":
        token = tokens[index]
        if token.type == "tr_open":
            cells = []
        elif token.type in ("th_open", "td_open"):
            content = tokens[index+1]
            cells.append(Paragraph(inline_markup(content.children),
                                   style["head" if token.type == "th_open" else "cell"]))
        elif token.type == "tr_close":
            rows.append(cells)
        elif token.type == "thead_close":
            headers = list(rows)
        index += 1
    count = len(rows[0])
    if count == 9:
        weights = [.8, 1.45, 1.05, 1.7, 1.75, 1.9, 1.7, .85, 1.1]
    elif count == 2:
        weights = [1, 2.3]
    elif count == 3:
        weights = [1.25, 1, 2]
    else:
        weights = [1] * count
    table = LongTable(rows, colWidths=[width*w/sum(weights) for w in weights],
                      repeatRows=len(headers), hAlign="LEFT", splitByRow=1, splitInRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, len(headers)-1), colors.HexColor("#17384e")),
        ("ROWBACKGROUNDS", (0, len(headers)), (-1, -1), [colors.white, colors.HexColor("#f3f6f8")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#cdd8df")),
    ]))
    return table, index


def markdown_to_pdf(markdown, output, *, label="", font_dir=None):
    register_fonts(font_dir)
    tokens = MarkdownIt("commonmark", {"html": False}).enable("table").parse(release_text(markdown))
    wide = any(t.type == "tr_open" and sum(x.type in ("th_open", "td_open")
               for x in tokens[i+1:next((j for j in range(i+1, len(tokens))
                                        if tokens[j].type == "tr_close"), len(tokens))]) >= 6
               for i, t in enumerate(tokens))
    page_size = landscape(A4) if wide else A4
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = DocumentTemplate(str(output), pagesize=page_size, leftMargin=17*mm, rightMargin=17*mm,
                           topMargin=22*mm, bottomMargin=19*mm,
                           title=label or output.stem, author="ATE Workbench", pageCompression=1,
                           invariant=1)
    style = styles()
    story, lists, pending_bullet = [], [], None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == "heading_open":
            level = min(int(token.tag[1:]), 3)
            heading = Paragraph(inline_markup(tokens[i+1].children), style[f"h{level}"])
            heading.heading_level = level-1
            story.append(heading)
            i += 2
        elif token.type in ("bullet_list_open", "ordered_list_open"):
            lists.append({"ordered": token.type == "ordered_list_open", "number": int(token.attrGet("start") or 1)})
        elif token.type in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
        elif token.type == "list_item_open":
            current = lists[-1]
            pending_bullet = f"{current['number']}." if current["ordered"] else "•"
            current["number"] += 1
        elif token.type == "list_item_close":
            pending_bullet = None
        elif token.type == "paragraph_open":
            paragraph_style = style["body"]
            if lists:
                paragraph_style = ParagraphStyle("List", parent=paragraph_style,
                    leftIndent=15*len(lists), bulletIndent=15*(len(lists)-1), spaceAfter=6)
            story.append(Paragraph(inline_markup(tokens[i+1].children), paragraph_style,
                                   bulletText=pending_bullet))
            pending_bullet = None
            i += 2
        elif token.type in ("fence", "code_block"):
            code = escape(token.content.rstrip()).replace(" ", "&#160;").replace("\n", "<br/>")
            story.append(Paragraph(code, style["code"]))
        elif token.type == "table_open":
            table, i = make_table(tokens, i, doc.width-12, style)
            table.spaceBefore, table.spaceAfter = 4, 12
            story.append(table)
        elif token.type == "hr":
            story.append(Spacer(1, 12))
        elif token.type == "blockquote_open":
            story.append(Spacer(1, 4))
        elif token.type not in ("blockquote_close",):
            raise ValueError(f"Unrendered Markdown block: {token.type}")
        i += 1
    while story and isinstance(story[-1], Spacer):
        story.pop()
    if not story:
        story.append(Paragraph("Empty document", style["body"]))

    def furniture(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d4dde4"))
        canvas.line(doc.leftMargin, page_size[1]-15*mm, page_size[0]-doc.rightMargin, page_size[1]-15*mm)
        canvas.setFont("BenchCJKBold", 8)
        canvas.setFillColor(colors.HexColor("#3e6075"))
        canvas.drawString(doc.leftMargin, page_size[1]-12*mm, "ATE WORKBENCH  /  DOCUMENTATION")
        canvas.setFont("BenchCJK", 7)
        canvas.setFillColor(colors.HexColor("#637583"))
        short_label = (label[-90:] if len(label) > 90 else label) or output.name
        canvas.drawString(doc.leftMargin, 10*mm, short_label)
        canvas.drawRightString(page_size[0]-doc.rightMargin, 10*mm, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=furniture, onLaterPages=furniture)
    return doc.page


def convert_release_documents(bundle):
    """Only mutate the caller's staged bundle, never the project's Markdown originals."""
    bundle = Path(bundle).resolve()
    records = {}
    previous = bundle/"docs/validation/release_documents.json"
    if previous.is_file():
        for record in json.loads(previous.read_text(encoding="utf-8")).get("converted", []):
            target = (bundle/record["pdf"]).resolve()
            if target.is_relative_to(bundle) and target.is_file():
                records[record["pdf"]] = record
    for source in sorted(bundle.rglob("*.md")):
        if not source.resolve().is_relative_to(bundle):
            raise ValueError(f"Markdown source escapes release directory: {source}")
        output = source.with_suffix(".pdf")
        raw = source.read_bytes()
        pages = markdown_to_pdf(raw.decode("utf-8-sig"), output,
                                label=output.relative_to(bundle).as_posix())
        records[output.relative_to(bundle).as_posix()] = {"source": source.relative_to(bundle).as_posix(),
                        "source_sha256": hashlib.sha256(raw).hexdigest(),
                        "pdf": output.relative_to(bundle).as_posix(), "pages": pages,
                        "pdf_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
        source.unlink()
    return sorted(records.values(), key=lambda item: item["pdf"])
