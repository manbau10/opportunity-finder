"""Detect required application materials and limits before drafting begins."""

from __future__ import annotations

import re


DOCUMENTS = {
    "cover_letter": "Cover Letter",
    "tailored_cv": "Tailored CV",
    "supporting_statement": "Supporting Statement",
    "selection_criteria": "Selection Criteria Response",
    "research_statement": "Research Statement",
    "research_plan": "Research Plan",
    "teaching_statement": "Teaching Statement",
    "diversity_statement": "Diversity Equity and Inclusion Statement",
    "outreach_statement": "Outreach and Engagement Statement",
    "leadership_statement": "Leadership Statement",
    "list_of_publications": "List of Publications",
    "references": "Referees and References",
}

PATTERNS = {
    "cover_letter": r"cover(?:ing)?\s+letter|letter\s+of\s+(?:application|interest)",
    "tailored_cv": r"curriculum\s+vitae|\bCV\b|résumé|resume",
    "supporting_statement": r"supporting\s+(?:statement|information)|personal\s+statement",
    "selection_criteria": r"selection\s+criteria|address\s+(?:the\s+)?(?:essential\s+)?criteria|"
                          r"response\s+to\s+(?:the\s+)?criteria",
    "research_statement": r"research\s+statement|statement\s+of\s+research",
    "research_plan": r"research\s+plan|future\s+research|research\s+proposal",
    "teaching_statement": r"teaching\s+(?:statement|philosophy)|statement\s+of\s+teaching",
    "diversity_statement": r"diversity\s+statement|dei\s+statement|equity.*inclusion\s+statement|"
                           r"contributions?\s+to\s+(?:diversity|inclusive excellence)",
    "outreach_statement": r"outreach\s+statement|community\s+engagement\s+statement|"
                          r"public\s+engagement\s+statement",
    "leadership_statement": r"leadership\s+statement|statement\s+of\s+leadership",
    "list_of_publications": r"publication\s+list|list\s+of\s+publications",
    "references": r"(?:three|3|two|2)\s+(?:professional\s+|academic\s+)?references|"
                  r"contact\s+details\s+for\s+(?:three|3|two|2)\s+referees|reference\s+list",
}


def _limit_near(text: str, pattern: str) -> str:
    for match in re.finditer(pattern, text, re.I):
        window = text[max(0, match.start() - 180):min(len(text), match.end() + 240)]
        word = re.search(r"(?:maximum|limit(?:ed)?\s+to|no\s+more\s+than|up\s+to)\s+"
                         r"([0-9,]+)\s*words?", window, re.I)
        page = re.search(r"(?:maximum|limit(?:ed)?\s+to|no\s+more\s+than|up\s+to)\s+"
                         r"([0-9]+)\s*pages?", window, re.I)
        if word:
            return f"{word.group(1)} words"
        if page:
            return f"{page.group(1)} pages"
    return ""


def detect_requirements(text: str, kind: str, requested: list[str] | None = None) -> dict:
    text = text or ""
    found = []
    for key, pattern in PATTERNS.items():
        if re.search(pattern, text, re.I):
            found.append({
                "key": key, "label": DOCUMENTS[key], "required": True,
                "detail": "Explicitly mentioned in the collected application material",
                "limit": _limit_near(text, pattern),
            })
    keys = {item["key"] for item in found}
    # An explicit UI/API selection is authoritative. Automatic defaults are used
    # only when the caller asks the application analyser to decide.
    defaults = list(requested or []) or ["cover_letter", "tailored_cv"]
    lower = text.lower()
    if not requested and kind == "academic" and not keys.intersection(
            {"supporting_statement", "selection_criteria", "research_statement", "research_plan"}):
        if any(term in lower for term in ("assistant professor", "tenure", "faculty position")):
            defaults += ["research_statement", "teaching_statement"]
        elif any(term in lower for term in ("person specification", "essential criteria", "senior lecturer", "lecturer")):
            defaults += ["supporting_statement"]
    elif (not requested and kind == "industry" and
          not keys.intersection({"supporting_statement", "selection_criteria"})):
        defaults += ["selection_criteria"]
    for key in defaults:
        if key in DOCUMENTS and key not in keys:
            found.append({
                "key": key, "label": DOCUMENTS[key], "required": key in {"tailored_cv"},
                "detail": "Included as a standard application document",
                "limit": "",
            })
            keys.add(key)
    return {
        "submission_items": found,
        "criteria": [],
        "gaps": [],
        "documents": [item["key"] for item in found],
    }


def merge_ai_plan(detected: dict, planned: dict) -> dict:
    """Merge AI extraction without allowing it to remove deterministic requirements."""
    result = {key: list(value) if isinstance(value, list) else value
              for key, value in detected.items()}
    items = {item["key"]: dict(item) for item in detected.get("submission_items", [])}
    for item in planned.get("submission_items", []) if isinstance(planned, dict) else []:
        key = item.get("key")
        if key in DOCUMENTS:
            base = items.get(key, {"key": key, "label": DOCUMENTS[key]})
            for field in ("required", "detail", "limit"):
                if item.get(field) not in (None, ""):
                    base[field] = item[field]
            items[key] = base
    result["submission_items"] = list(items.values())
    result["documents"] = list(items)
    if isinstance(planned, dict):
        result["criteria"] = [x for x in planned.get("criteria", []) if isinstance(x, dict)][:35]
        result["gaps"] = [str(x) for x in planned.get("gaps", []) if str(x).strip()][:15]
        result["cv_edits"] = planned.get("cv_edits", {}) if isinstance(planned.get("cv_edits"), dict) else {}
    return result
