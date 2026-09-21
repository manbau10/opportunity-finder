"""Deterministic Microsoft Word builders used by application packs."""

from __future__ import annotations

import io
import re

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def add_hyperlink(paragraph, text: str, url: str) -> None:
    part = paragraph.part
    rel_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rel_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color"); color.set(qn("w:val"), "1F5E4B")
    underline = OxmlElement("w:u"); underline.set(qn("w:val"), "single")
    props.extend([color, underline]); run.append(props)
    node = OxmlElement("w:t"); node.text = text
    run.append(node); hyperlink.append(run); paragraph._p.append(hyperlink)


def base_doc(title: str, subtitle: str = "") -> Document:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(0.8)
    section.left_margin = section.right_margin = Inches(0.85)
    styles = doc.styles
    styles["Normal"].font.name = "Aptos"; styles["Normal"].font.size = Pt(11)
    styles["Normal"].paragraph_format.space_after = Pt(8)
    for style_name in ("Title", "Heading 1", "Heading 2"):
        styles[style_name].font.name = "Aptos Display"
        styles[style_name].font.color.rgb = RGBColor(0, 0, 0)
    title_p = doc.add_paragraph(style="Title")
    title_p.add_run(title)
    if subtitle:
        doc.add_paragraph(subtitle, style="Subtitle")
    return doc


def docx_bytes(title: str, content: str, subtitle: str = "") -> bytes:
    doc = base_doc(title, subtitle)
    for block in re.split(r"\n\s*\n", (content or "").strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            doc.add_heading(block[3:].strip(), level=1)
        elif block.startswith("### "):
            doc.add_heading(block[4:].strip(), level=2)
        elif all(line.lstrip().startswith(("- ", "* ")) for line in block.splitlines()):
            for line in block.splitlines():
                doc.add_paragraph(line.lstrip()[2:], style="List Bullet")
        else:
            doc.add_paragraph(block)
    output = io.BytesIO(); doc.save(output); return output.getvalue()


def sources_doc(sources: list[dict], opportunity: dict) -> bytes:
    doc = base_doc("Application Research Sources",
                   f"Sources collected for {opportunity.get('title', 'the role')}")
    doc.add_paragraph(
        "Review these sources before submitting. They are included so every factual statement "
        "introduced during drafting can be checked against its original page.")
    for n, source in enumerate(sources, 1):
        doc.add_heading(f"Source {n} {source.get('title') or 'Untitled'}", level=1)
        if source.get("url"):
            p = doc.add_paragraph(); add_hyperlink(p, source["url"], source["url"])
        doc.add_paragraph(f"Search query: {source.get('query', '')}")
        doc.add_paragraph(source.get("snippet") or "No search excerpt was available.")
        doc.add_paragraph(f"Retrieved: {source.get('retrieved_at', '')}")
    output = io.BytesIO(); doc.save(output); return output.getvalue()


def job_doc(opportunity: dict) -> bytes:
    body = (
        f"## Role\n\n{opportunity.get('title','')}\n\n"
        f"## Employer\n\n{opportunity.get('org','')}\n\n"
        f"## Location and deadline\n\n{opportunity.get('location','')} | {opportunity.get('deadline') or 'Not stated'}\n\n"
        f"## Original advert\n\n{opportunity.get('url','')}\n\n"
        f"## Advert text\n\n{opportunity.get('description','')}"
    )
    return docx_bytes("Job Advertisement Snapshot", body)

