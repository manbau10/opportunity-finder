# -*- coding: utf-8 -*-
"""Subject vocabulary used to turn a CV into search phrases.

Matching a CV against this list produces clean, searchable phrases such as
"water infrastructure" instead of loose words such as "for" or an author's
surname. It covers many professions, not one person's field.
"""

from __future__ import annotations

SUBJECT_PHRASES = [
    # built environment, engineering, energy
    "construction management", "construction engineering", "civil engineering",
    "infrastructure engineering", "infrastructure management", "infrastructure asset management",
    "water infrastructure", "water resources", "water distribution", "wastewater",
    "asset management", "built environment", "building information modelling",
    "building information modeling", "digital twin", "structural engineering",
    "geotechnical engineering", "transport infrastructure", "transportation engineering",
    "environmental engineering", "quantity surveying", "facilities management",
    "sustainable construction", "modular construction", "offsite construction",
    "mechanical engineering", "electrical engineering", "chemical engineering",
    "materials science", "renewable energy", "power systems", "energy systems",
    "systems engineering", "industrial engineering", "aerospace engineering",
    "biomedical engineering", "process engineering", "petroleum engineering",
    "mining engineering", "marine engineering", "robotics", "control systems",
    "urban planning", "architecture", "landscape architecture", "geomatics",
    "hydrology", "hydraulics", "climate change", "remote sensing",
    # computing and data
    "machine learning", "deep learning", "artificial intelligence", "data science",
    "data analytics", "natural language processing", "computer vision",
    "software engineering", "cyber security", "cybersecurity", "cloud computing",
    "distributed systems", "human computer interaction", "databases",
    "information systems", "bioinformatics", "statistics", "operations research",
    "optimisation", "optimization", "simulation", "internet of things",
    # sciences
    "molecular biology", "cell biology", "genetics", "genomics", "microbiology",
    "biochemistry", "neuroscience", "immunology", "ecology", "plant science",
    "organic chemistry", "analytical chemistry", "physical chemistry",
    "condensed matter", "particle physics", "astrophysics", "quantum computing",
    "applied mathematics", "pure mathematics", "earth science", "geology",
    "oceanography", "atmospheric science", "environmental science", "public health",
    "epidemiology", "pharmacology", "toxicology",
    # health
    "clinical practice", "nursing", "midwifery", "mental health", "paediatrics",
    "physiotherapy", "occupational therapy", "radiography", "pharmacy",
    "medical education", "health policy", "critical care",
    # business, social science, humanities, law
    "project management", "programme management", "risk management",
    "supply chain", "operations management", "financial management", "accounting",
    "auditing", "corporate finance", "financial analysis", "marketing",
    "human resources", "organisational behaviour", "business administration",
    "entrepreneurship", "economics", "econometrics", "development economics",
    "international relations", "political science", "public policy", "sociology",
    "anthropology", "psychology", "social work", "criminology", "linguistics",
    "english literature", "law",
    "international law", "human rights", "curriculum development",
    "teacher education", "higher education", "library science", "journalism",
    "media studies", "fine art",
    "stakeholder management", "contract management", "cost management",
    "procurement", "health and safety", "sustainability", "quality assurance",
]

# Words that carry no subject information in a CV.
NOISE_WORDS = {
    "about", "above", "across", "after", "again", "against", "all", "also",
    "among", "and", "any", "are", "around", "because", "been", "before",
    "being", "below", "between", "both", "but", "can", "could", "did", "does",
    "doi", "during", "each", "etc", "few", "for", "from", "further", "had",
    "has", "have", "having", "her", "here", "hers", "him", "his", "how",
    "http", "https", "into", "its", "just", "may", "more", "most", "much",
    "must", "new", "nor", "not", "now", "off", "once", "one", "only", "other",
    "our", "out", "over", "own", "per", "same", "she", "should", "since",
    "some", "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "through", "too", "under", "until",
    "upon", "very", "was", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "within", "without", "would", "you",
    "your", "www", "com", "org", "edu", "pdf", "via", "using", "used", "use",
    "based", "present", "current", "currently", "top", "percentile", "journal",
    "journals", "article", "articles", "paper", "papers", "conference",
    "proceedings", "reviewer", "review", "reviews", "january", "february",
    "march", "april", "june", "july", "august", "september", "october",
    "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
    "sep", "sept", "oct", "nov", "dec", "year", "years", "month", "months",
    "experience", "work", "worked", "working", "university", "college",
    "school", "department", "faculty", "institute", "responsible", "including",
    "include", "includes", "provided", "provide", "support", "supported",
    "assisted", "developed", "development", "various", "key", "main", "role",
    "roles", "team", "teams", "skills", "skill", "summary", "profile",
    "references", "available", "request", "email", "phone",
    "tel", "mobile", "address", "contact", "page", "pages", "vol", "issue",
    "pp", "no", "ieee", "elsevier", "springer", "wiley", "mdpi", "asce",
    "published", "publication", "publications", "citation", "citations",
}
