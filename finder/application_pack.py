"""Generate auditable Word application packs and persist the ZIP privately."""

from __future__ import annotations

import base64
import datetime as dt
import io
import json
import re
import threading
import uuid
import zipfile

from . import store
from .auth import now
from .docgen import docx_bytes, job_doc, sources_doc
from .profiles import get_profile
from .providers import chat
from .research import research_opportunity

PACK_LOCK = threading.Lock()
ALLOWED_DOCS = {
    "cover_letter", "tailored_cv", "research_statement", "teaching_statement",
    "supporting_statement", "selection_criteria",
}


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value or "")
    return re.sub(r"\s+", "_", value.strip())[:80] or "Application"


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("The AI provider did not return the requested JSON document set.")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("The AI provider returned an invalid document set.")
    return value


def _default_docs(kind: str) -> list[str]:
    return (["cover_letter", "tailored_cv", "research_statement", "teaching_statement",
             "supporting_statement"] if kind == "academic" else
            ["cover_letter", "tailored_cv", "selection_criteria"])


def _generate(pack_id: str, user_id: str, opportunity_id: str, kind: str,
              requested: list[str]) -> None:
    conn = store.connect()
    try:
        row = conn.execute("SELECT * FROM opportunities WHERE id=? AND career_track=?",
                           (opportunity_id, kind)).fetchone()
    finally:
        conn.close()
    if not row:
        _fail(pack_id, "Opportunity was not found for this career track."); return
    opportunity = store.decode(row)
    profile = get_profile(user_id, kind, include_text=True)
    if not profile:
        _fail(pack_id, f"Upload your {kind} CV first."); return
    try:
        sources = research_opportunity(user_id, opportunity)
        docs = [d for d in requested if d in ALLOWED_DOCS] or _default_docs(kind)
        source_text = "\n".join(
            f"[{n}] {s.get('title')} | {s.get('url')} | {s.get('snippet')}"
            for n, s in enumerate(sources, 1))
        system = (
            "You are an exacting job-application writer. Use only facts present in the CV, "
            "job advert and supplied research excerpts. Never invent achievements, metrics, "
            "publications, courses taught, responsibilities or qualifications. If evidence is "
            "missing, write a restrained transferable-skills sentence or omit the claim. Return "
            "valid JSON only. Use plain text with ## headings and blank-line paragraphs inside values.")
        prompt = f"""Create a tailored {kind} application package.

Requested JSON keys: {json.dumps(docs)}

CV:
{profile.get('cv_text','')[:70000]}

JOB:
Title: {opportunity.get('title')}
Employer: {opportunity.get('org')}
Department: {opportunity.get('department')}
Location: {opportunity.get('location')}
Deadline: {opportunity.get('deadline')}
Advert: {opportunity.get('description','')[:30000]}
URL: {opportunity.get('url')}

RESEARCH SOURCES:
{source_text[:20000]}

Return one JSON object. Each requested key must contain a complete document draft. Mention source
facts naturally but do not put raw URLs in cover letters or statements. The separate sources file
will preserve the URLs. The tailored_cv must retain factual detail from the CV and must not add facts.
"""
        labels = {
            "cover_letter": "Cover Letter", "tailored_cv": "Tailored CV",
            "research_statement": "Research Statement", "teaching_statement": "Teaching Statement",
            "supporting_statement": "Supporting Statement", "selection_criteria": "Selection Criteria",
        }
        generated = _extract_json(chat(user_id, system, prompt))
        missing = [labels.get(key, key) for key in docs
                   if not isinstance(generated.get(key), str) or len(generated[key].strip()) < 80]
        if missing:
            raise ValueError("AI provider omitted required documents: " + ", ".join(missing))
        zip_buffer = io.BytesIO()
        document_names = []
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for key in docs:
                content = generated.get(key)
                if not isinstance(content, str) or len(content.strip()) < 80:
                    continue
                filename = _safe_name(labels[key]) + ".docx"
                zf.writestr(filename, docx_bytes(labels[key], content,
                    f"Prepared for {opportunity.get('org','the employer')}"))
                document_names.append(filename)
            zf.writestr("Research Sources.docx", sources_doc(sources, opportunity))
            zf.writestr("Job Advertisement.docx", job_doc(opportunity))
            manifest = {
                "generated_at": now(), "profile_kind": kind,
                "opportunity": {k: opportunity.get(k) for k in
                    ("id", "title", "org", "department", "location", "deadline", "url")},
                "documents": document_names + ["Research Sources.docx", "Job Advertisement.docx"],
                "source_count": len(sources),
                "review_notice": "Review every document and source before submitting. AI output may contain errors.",
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            zf.writestr("README.txt",
                "Review and edit every Word document before applying.\n"
                "Research Sources.docx lists the online material used during drafting.\n"
                "The applicant remains responsible for accuracy and submission requirements.\n")
        conn = store.connect()
        try:
            conn.execute(
                """UPDATE application_packs SET status='ready',documents_json=?,sources_json=?,
                   zip_blob=?,completed_at=?,error=NULL WHERE id=? AND user_id=?""",
                (json.dumps(document_names), json.dumps(sources),
                 base64.b64encode(zip_buffer.getvalue()).decode("ascii"), now(), pack_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        _fail(pack_id, f"{type(exc).__name__}: {exc}")


def _fail(pack_id: str, error: str) -> None:
    conn = store.connect()
    try:
        conn.execute("UPDATE application_packs SET status='failed',error=?,completed_at=? WHERE id=?",
                     (error[:1200], now(), pack_id))
        conn.commit()
    finally:
        conn.close()


def start_pack(user_id: str, opportunity_id: str, kind: str, documents: list[str]) -> str:
    pack_id = uuid.uuid4().hex
    conn = store.connect()
    try:
        conn.execute(
            """INSERT INTO application_packs
               (id,user_id,opportunity_id,profile_kind,status,created_at)
               VALUES (?,?,?,?,?,?)""",
            (pack_id, user_id, opportunity_id, kind, "working", now()),
        )
        conn.commit()
    finally:
        conn.close()
    threading.Thread(target=_generate, args=(pack_id, user_id, opportunity_id, kind, documents),
                     daemon=True, name=f"pack-{pack_id[:8]}").start()
    return pack_id


def get_pack(user_id: str, pack_id: str, include_blob: bool = False) -> dict | None:
    fields = "*" if include_blob else "id,user_id,opportunity_id,profile_kind,status,documents_json,sources_json,error,created_at,completed_at"
    conn = store.connect()
    try:
        row = conn.execute(f"SELECT {fields} FROM application_packs WHERE id=? AND user_id=?",
                           (pack_id, user_id)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None
