"""Occupational-domain classification used before keyword similarity scoring.

The matcher deliberately treats job titles as stronger evidence than advert copy.
This prevents incidental words such as "care", "health" or "project" from making an
unrelated role look suitable.
"""

from __future__ import annotations

import re


DOMAIN_LABELS = {
    "nursing": "Nursing",
    "allied_health": "Allied health / clinical",
    "construction": "Construction and infrastructure",
    "project_management": "Project and programme management",
    "data": "Data and analytics",
    "software": "Software and technology",
    "finance": "Finance and accounting",
    "marketing": "Marketing, sales and communications",
    "hr": "Human resources",
    "education": "Education and research",
    "operations": "Operations and administration",
}

# Patterns are intentionally occupation-specific. Broad words such as care, health,
# digital and management are excluded because they create misleading matches.
DOMAIN_PATTERNS = {
    "nursing": [
        r"\bregistered nurse\b", r"\bstaff nurse\b", r"\bclinical nurse\b",
        r"\bnurse practitioner\b", r"\bnurse educator\b", r"\bnursing officer\b",
        r"\bnursing\b", r"\bnurse\b", r"\bmidwi(?:fe|fery|ves)\b",
        r"\bward sister\b", r"\bhealth visitor\b", r"\bmental health nurse\b",
        r"\bpaediatric nurse\b", r"\bpediatric nurse\b",
    ],
    "allied_health": [
        r"\bphysiotherap", r"\boccupational therapist\b", r"\bradiograph",
        r"\bpharmac(?:ist|y)\b", r"\bparamedic\b", r"\bsocial worker\b",
        r"\bspeech (?:and language )?therap", r"\bmedical laboratory\b",
        r"\bclinical psychologist\b", r"\bphysician\b", r"\bmedical doctor\b",
    ],
    "construction": [
        r"\bconstruction (?:manager|management|engineer|engineering|project)\b",
        r"\bcivil engineer", r"\binfrastructure (?:engineer|manager|management|project)",
        r"\bquantity survey", r"\bbuilding survey", r"\bstructural engineer",
        r"\bwater (?:infrastructure|resources|engineer)", r"\bbuilt environment\b",
        r"\btransport(?:ation)? infrastructure\b", r"\bconstruction\b",
    ],
    "project_management": [
        r"\bproject manager\b", r"\bprogramme manager\b", r"\bprogram manager\b",
        r"\bproject management\b", r"\bprogramme management\b", r"\bpmo\b",
    ],
    "data": [
        r"\bdata analyst\b", r"\bdata scientist\b", r"\banalytics engineer\b",
        r"\bbusiness intelligence\b", r"\bbi analyst\b", r"\bstatistician\b",
        r"\bmachine learning engineer\b", r"\bdata engineer\b",
    ],
    "software": [
        r"\bsoftware (?:engineer|developer|architect)\b", r"\bfront[ -]?end developer\b",
        r"\bback[ -]?end developer\b", r"\bfull[ -]?stack\b", r"\bdevops\b",
        r"\bcloud engineer\b", r"\bplatform engineer\b", r"\bweb developer\b",
        r"\bproduct manager\b", r"\be-?commerce\b",
    ],
    "finance": [
        r"\baccountant\b", r"\bauditor\b", r"\bfinancial analyst\b",
        r"\bfinance manager\b", r"\bbookkeeper\b", r"\bactuar",
    ],
    "marketing": [
        r"\bmarketing (?:manager|specialist|executive)\b", r"\bsales (?:manager|executive)\b",
        r"\bcommunications? manager\b", r"\bbrand manager\b", r"\bcopywriter\b",
        r"\bsocial media manager\b",
    ],
    "hr": [
        r"\bhuman resources\b", r"\bhr (?:manager|advisor|business partner)\b",
        r"\brecruiter\b", r"\btalent acquisition\b", r"\bpeople partner\b",
    ],
    "education": [
        r"\bteacher\b", r"\bprofessor\b", r"\blecturer\b",
        r"\bpostdoctoral\b", r"\bresearch fellow\b", r"\bresearch associate\b",
    ],
    "operations": [
        r"\boperations manager\b", r"\badministrative assistant\b",
        r"\boffice manager\b", r"\bcustomer success\b", r"\bcustomer support\b",
        r"\bsupply chain\b", r"\blogistics manager\b",
    ],
}


TARGET_TITLES = {
    "nursing": ["registered nurse", "staff nurse", "clinical nurse", "nurse practitioner",
                "nursing officer", "nurse educator", "community nurse", "ward nurse",
                "mental health nurse", "midwife"],
    "allied_health": ["clinical specialist", "healthcare practitioner", "therapist"],
    "construction": ["project manager", "construction manager", "infrastructure manager",
                     "programme manager", "civil engineer", "asset manager"],
    "project_management": ["project manager", "programme manager", "program manager", "pmo"],
    "data": ["data analyst", "data scientist", "business intelligence analyst", "data engineer"],
    "software": ["software engineer", "software developer", "platform engineer", "product manager"],
    "finance": ["accountant", "financial analyst", "finance manager", "auditor"],
    "marketing": ["marketing manager", "marketing specialist", "communications manager"],
    "hr": ["human resources", "hr manager", "recruiter", "talent acquisition"],
    "operations": ["operations manager", "administrator", "office manager"],
}


def classify(text: str, *, title: bool = False) -> dict[str, int]:
    """Return evidence counts by occupational domain."""
    value = (text or "").lower()
    scores: dict[str, int] = {}
    for domain, patterns in DOMAIN_PATTERNS.items():
        hits = sum(len(re.findall(pattern, value, flags=re.I)) for pattern in patterns)
        if hits:
            scores[domain] = hits * (4 if title else 1)
    return scores


def ranked_domains(text: str) -> list[dict]:
    scores = classify(text)
    return [
        {"key": key, "label": DOMAIN_LABELS[key], "score": score}
        for key, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]


def primary_domain(text: str) -> str:
    ranked = ranked_domains(text)
    if not ranked:
        return "general"
    # Education wording is common in academic CVs and should not displace the
    # candidate's subject profession when another domain is present.
    for item in ranked:
        if item["key"] != "education":
            return item["key"]
    return ranked[0]["key"]


def job_domain_evidence(title: str, description: str = "") -> tuple[dict[str, int], dict[str, int]]:
    return classify(title, title=True), classify(description)
