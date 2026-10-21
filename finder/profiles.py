"""CV ingestion and structured profile extraction."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import uuid
from collections import Counter

from . import store
from .auth import now
from .domains import DOMAIN_LABELS, TARGET_TITLES, primary_domain, ranked_domains
from .vocab import NOISE_WORDS, SUBJECT_PHRASES

# Bump when keyword/title extraction improves; stored profiles are upgraded on next read.
PROFILE_VERSION = 2
MAX_CV_BYTES = 6 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md"}

TITLE_WORDS = re.compile(
    r"\b(?:manager|engineer|nurse|analyst|specialist|officer|coordinator|consultant|"
    r"developer|designer|technician|accountant|auditor|teacher|lecturer|professor|"
    r"therapist|pharmacist|surveyor|architect|administrator|director|supervisor|"
    r"scientist|researcher|planner|advisor|assistant|practitioner|midwife)\b", re.I)


def _infer_job_titles(text: str) -> list[str]:
    """Extract plausible role lines as a universal fallback for unknown fields."""
    titles = []
    for raw in text.splitlines():
        line = " ".join(raw.strip(" -|•	").split())
        # "Site Engineer (03/2019-01/2020)" -> "Site Engineer"
        line = re.sub(r"\s*[\(\[].*$", "", line)
        line = re.sub(r"\s*[|–—,:;].*$", "", line).strip(" -.")
        words = line.split()
        if not (2 <= len(words) <= 6 and len(line) <= 70 and TITLE_WORDS.search(line)):
            continue
        if re.search(r"\d|@|http|&|nanodegree|certificate|course|founder|volunteer", line, re.I):
            continue
        if re.search(r"\b(?:responsibilit|experience|education|profile|summary|skills|"
                     r"reviewer|referee|reference|journal|conference)\b", line, re.I):
            continue
        if line.lower() not in {x.lower() for x in titles}:
            titles.append(line)
    return titles[:8]


def _word_forms(text: str) -> tuple[Counter, Counter]:
    """Count lower-case and Capitalised occurrences of each word.

    A word that only ever appears Capitalised in a CV is almost always a name
    (an author, institution or heading), not a subject, so it is not a keyword.
    """
    lower: Counter = Counter()
    cap: Counter = Counter()
    for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text):
        key = token.lower()
        if token.islower():
            lower[key] += 1
        elif token[0].isupper() and token[1:].islower():
            cap[key] += 1
    return lower, cap


def _keywords(text: str) -> list[str]:
    lower_text = text.lower()
    lower, _cap = _word_forms(text)

    def usable(word: str) -> bool:
        return (len(word) >= 4 and word not in NOISE_WORDS and lower[word] >= 1
                and not word.isdigit())

    phrase_counts = {}
    for phrase in SUBJECT_PHRASES:
        found = len(re.findall(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", lower_text))
        # A one-word subject such as "law" or "design" must recur to count.
        if found >= (1 if " " in phrase else 3):
            phrase_counts[phrase] = found
    phrase_hits = sorted(phrase_counts, key=lambda p: -phrase_counts[p])

    bigrams: Counter = Counter()
    for line in text.splitlines():
        tokens = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'-]{2,}|[,;:.()]", line)]
        for a, b in zip(tokens, tokens[1:]):
            if usable(a) and usable(b):
                bigrams[f"{a} {b}"] += 1
    pairs = [p for p, n in bigrams.most_common(60) if n >= 2 and p not in phrase_hits]

    singles = [w for w, n in lower.most_common(120) if usable(w) and n >= 3]
    ordered = phrase_hits + pairs[:14] + singles[:24]
    return list(dict.fromkeys(ordered))[:60]


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def extract_text(data: bytes, filename: str) -> tuple[str, str]:
    if not data or len(data) > MAX_CV_BYTES:
        raise ValueError("CV files must be between 1 byte and 6 MB.")
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Upload a PDF, DOCX, TXT or Markdown CV.")
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        mime = "application/pdf"
    elif ext == "docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        chunks = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                chunks.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(chunks)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        text = data.decode("utf-8", errors="replace")
        mime = "text/plain"
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 120:
        raise ValueError("Very little readable text was found in this CV.")
    return text[:250000], mime


def build_profile(text: str, kind: str) -> dict:
    lower = text.lower()
    words = re.findall(r"[a-z][a-z0-9+#.-]{2,}", lower)
    keywords = _keywords(text)
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phones = re.findall(r"(?:\+?\d[\d ()-]{7,}\d)", text)
    degree = "PhD" if re.search(r"\b(ph\.?d|doctor of philosophy)\b", lower) else (
        "Master's" if re.search(r"\b(m\.?sc|m\.?eng|master)\b", lower) else "")
    domain = primary_domain(text)
    # Student and support roles on a CV (teaching assistant, hall coordinator, intern)
    # are not what the person is job-hunting for, so they are not used as search titles.
    inferred_titles = [t for t in _infer_job_titles(text)
                       if not re.search(r"assistant|teaching|student|intern|tutor|trainee|"
                                        r"apprentice|fellow|coordinator", t, re.I)]
    subject_titles = list(dict.fromkeys(TARGET_TITLES.get(domain, []) + inferred_titles))
    target_titles = (
        ["assistant professor", "lecturer", "research fellow", "postdoctoral fellow"]
        if kind == "academic" else subject_titles
    )
    return {
        "kind": kind,
        "extractor_version": PROFILE_VERSION,
        "keywords": keywords,
        "target_titles": target_titles,
        "preferred_locations": [],
        "primary_domain": domain,
        "domain_label": DOMAIN_LABELS.get(domain, "General / multidisciplinary"),
        "domains": ranked_domains(text)[:5],
        "degree": degree,
        "email": emails[0] if emails else "",
        "phone": phones[0].strip() if phones else "",
        "word_count": len(words),
    }


def save_profile(user_id: str, kind: str, filename: str, data: bytes) -> dict:
    if kind not in ("academic", "industry"):
        raise ValueError("Unknown CV type.")
    text, mime = extract_text(data, filename)
    profile = build_profile(text, kind)
    stamp = now()
    digest = hashlib.sha256(data).hexdigest()
    conn = store.connect()
    try:
        old = conn.execute(
            "SELECT id,created_at FROM user_profiles WHERE user_id=? AND kind=?",
            (user_id, kind),
        ).fetchone()
        if old:
            profile_id, created = old["id"], old["created_at"]
            conn.execute(
                """UPDATE user_profiles SET cv_filename=?,cv_mime=?,cv_sha256=?,
                   cv_blob=?,cv_text=?,profile_json=?,updated_at=? WHERE id=? AND user_id=?""",
                (filename[:240], mime, digest, base64.b64encode(data).decode("ascii"), text,
                 json.dumps(profile), stamp, profile_id, user_id),
            )
        else:
            profile_id, created = uuid.uuid4().hex, stamp
            conn.execute(
                """INSERT INTO user_profiles
                   (id,user_id,kind,cv_filename,cv_mime,cv_sha256,cv_blob,cv_text,
                    profile_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (profile_id, user_id, kind, filename[:240], mime, digest,
                 base64.b64encode(data).decode("ascii"), text, json.dumps(profile),
                 created, stamp),
            )
        conn.commit()
    finally:
        conn.close()
    return {"id": profile_id, "kind": kind, "filename": filename, "profile": profile,
            "created_at": created, "updated_at": stamp}


def get_profile(user_id: str, kind: str, include_text: bool = False,
                include_blob: bool = False) -> dict | None:
    # Always fetch the extracted text so profiles created before occupational
    # classification was introduced can be upgraded transparently.
    fields = (
        "id,user_id,kind,cv_filename,cv_mime,cv_sha256,profile_json,"
        "created_at,updated_at" + (",cv_text" if include_text else "")
        + (",cv_blob" if include_blob else "")
    )
    conn = store.connect()
    try:
        row = conn.execute(
            f"SELECT {fields} FROM user_profiles WHERE user_id=? AND kind=?",
            (user_id, kind),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    result = dict(row)
    result["profile"] = json.loads(result.pop("profile_json") or "{}")
    current = result["profile"]
    if (not current.get("primary_domain")
            or current.get("extractor_version") != PROFILE_VERSION):
        if "cv_text" not in result:             # only an outdated profile needs the CV text
            conn = store.connect()
            try:
                found = conn.execute("SELECT cv_text FROM user_profiles WHERE id=? AND user_id=?",
                                     (result["id"], user_id)).fetchone()
            finally:
                conn.close()
            result["cv_text"] = (found["cv_text"] if found else "") or ""
        rebuilt = build_profile(result.get("cv_text") or "", kind)
        # Whatever the person typed on the CV page is theirs and is kept.
        rebuilt["preferred_locations"] = current.get("preferred_locations") or []
        if current.get("preferences_saved"):
            rebuilt["target_titles"] = current.get("target_titles") or rebuilt["target_titles"]
            rebuilt["preferences_saved"] = True
        result["profile"] = rebuilt
        conn = store.connect()
        try:
            conn.execute("UPDATE user_profiles SET profile_json=?,updated_at=? WHERE id=? AND user_id=?",
                         (json.dumps(rebuilt), now(), result["id"], user_id))
            conn.commit()
        finally:
            conn.close()
    if not include_text:
        result.pop("cv_text", None)
    return result


def profile_summaries(user_id: str) -> dict:
    return {kind: get_profile(user_id, kind) for kind in ("academic", "industry")}


def update_preferences(user_id: str, kind: str, data: dict) -> dict:
    if kind not in ("academic", "industry"):
        raise ValueError("Unknown CV type.")
    current = get_profile(user_id, kind, include_text=True)
    if not current:
        raise ValueError("Upload this CV before setting job preferences.")

    def clean_list(value, maximum: int) -> list[str]:
        raw = value if isinstance(value, list) else re.split(r"[,;\n]", str(value or ""))
        cleaned = []
        for entry in raw:
            item = " ".join(str(entry).split()).strip()[:100]
            if item and item.lower() not in {x.lower() for x in cleaned}:
                cleaned.append(item)
        return cleaned[:maximum]

    target_titles = clean_list(data.get("target_titles"), 12)
    if not target_titles:
        raise ValueError("Enter at least one target job title.")
    preferred_locations = clean_list(data.get("preferred_locations"), 12)
    profile = current["profile"]
    profile["target_titles"] = target_titles
    profile["preferred_locations"] = preferred_locations
    profile["preferences_saved"] = True
    stamp = now()
    conn = store.connect()
    try:
        conn.execute(
            "UPDATE user_profiles SET profile_json=?,updated_at=? WHERE id=? AND user_id=?",
            (json.dumps(profile), stamp, current["id"], user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"profile": profile, "updated_at": stamp}
