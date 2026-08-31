# -*- coding: utf-8 -*-
"""
Candidate profile derived from Ridwan Ademola Taiwo's CV.

Everything the scorer knows about the candidate lives here. Edit the weights
and term lists below to re-tune matching; nothing else needs to change.
"""

CANDIDATE = {
    "name": "Ridwan Ademola Taiwo",
    "current_role": "Postdoctoral Fellow, Dept. of Construction Management and Intelligence, PolyU",
    "phd": "PhD Infrastructure Engineering and Management, The Hong Kong Polytechnic University (2025)",
    "metrics": {"journal_articles": 50, "h_index": 21, "citations": 1780, "q1_articles": 39},
    "career_stage": "Early career - PhD 2025, first postdoc, 50 journal articles, h-index 21",
}

# ---------------------------------------------------------------------------
# Topic model
# ---------------------------------------------------------------------------
# Tier A: the candidate's own published niche - a hit here is decisive.
# Tier B: adjacent domains he has published in or taught.
# Tier C: methods he applies (they count less on their own).
# Tier D: weak contextual signals.

TIER_A = {
    "water pipe failure": 12, "water distribution network": 12, "water distribution system": 12,
    "water infrastructure": 12, "watermain": 12, "water main": 11, "leak detection": 12,
    "pipe failure": 11, "pipeline integrity": 10, "buried infrastructure": 10,
    "infrastructure asset management": 12, "asset management": 9,
    "infrastructure management": 11, "infrastructure engineering": 11,
    "construction management": 12, "construction engineering": 12,
    "construction informatics": 11, "construction automation": 10,
    "modular integrated construction": 11, "modular construction": 10,
    "offsite construction": 10, "off-site construction": 10,
    "industrialised construction": 10, "industrialized construction": 10,
    "modern methods of construction": 10,
    "infrastructure systems": 10, "civil infrastructure": 11,
    "water resources engineering": 10, "urban water": 11,
    "predictive maintenance": 10, "condition assessment": 9,
    "deterioration model": 10, "renewal planning": 9,
}

TIER_B = {
    "civil engineering": 7, "built environment": 7, "project management": 7,
    "construction project": 7, "construction industry": 6, "quantity surveying": 5,
    "building information modelling": 6, "building information modeling": 6,
    "digital twin": 6, "smart city": 5, "smart infrastructure": 7,
    "structural health monitoring": 6, "structural engineering": 5,
    "transport infrastructure": 6, "transportation engineering": 6,
    "pavement": 6, "highway": 5, "bridge engineering": 5, "railway": 5,
    "rail infrastructure": 5,
    "geotechnical": 5, "landslide": 5, "tunnelling": 5, "tunneling": 5,
    "construction materials": 6, "concrete": 5, "cement": 4,
    "circular economy": 6, "construction waste": 6, "solid waste": 5,
    "wastewater": 7, "sewer": 7, "drainage": 5, "stormwater": 6,
    "hydrology": 5, "hydraulics": 5, "water quality": 4, "water treatment": 4,
    "water supply": 7, "water utility": 7, "water management": 6,
    "climate resilience": 6, "resilient infrastructure": 8,
    "sustainable construction": 7, "sustainable infrastructure": 8,
    "net zero": 5, "decarbonisation": 4, "decarbonization": 4,
    "reliability engineering": 6, "risk assessment": 5, "risk management": 5,
    "life cycle assessment": 5, "whole life costing": 5,
    "urban planning": 4, "urban systems": 5, "public works": 5,
    "construction safety": 6, "health and safety": 4,
    "facility management": 5, "building engineering": 5,
    "engineering management": 7, "systems engineering": 4,
    "utility network": 7, "municipal engineering": 7,
    "surveying": 4, "contract administration": 6, "procurement": 4,
}

TIER_C = {
    "machine learning": 4, "artificial intelligence": 4, "deep learning": 4,
    "explainable ai": 5, "large language model": 5, "generative ai": 5,
    "computer vision": 4, "data-driven": 3, "data driven": 3, "data science": 3,
    "digitalisation": 3, "digitalization": 3, "decision support": 4,
    "optimisation": 3, "optimization": 3, "simulation": 3,
    "uncertainty quantification": 4, "predictive analytics": 4,
    "digital transformation": 3, "internet of things": 3, "remote sensing": 3,
    "bayesian": 3, "agent-based": 3, "sensor network": 3,
}

TIER_D = {
    "infrastructure": 2.5, "construction": 2.5, "water": 2.0,
    "engineering": 1.5, "sustainability": 1.5, "environmental": 1.5,
    "energy": 1.0, "urban": 1.0, "built": 1.0,
}

# Short terms that must be matched as standalone words, not substrings.
WORD_BOUNDARY_TERMS = {"bim", "water", "energy", "urban", "built", "concrete",
                       "cement", "pavement", "highway", "railway", "surveying",
                       "procurement", "engineering", "construction", "infrastructure",
                       "environmental", "sustainability", "bayesian", "simulation"}

# Extra terms scored only as whole words (kept out of the tier dicts so the
# substring scanner never fires on them by accident).
TIER_B_WORDS = {"bim": 6}

# Titles that clearly belong to another discipline. A match in the job TITLE
# strongly suppresses the score, because body text may mention "engineering"
# or "management" incidentally.
OFF_FIELD_TITLE_TERMS = [
    "nursing", "nurse", "midwifery", "medicine", "medical", "clinical trial",
    "dentistry", "dental", "pharmacy", "pharmaceutic", "veterinary", "anatomy",
    "physiology", "oncology", "cardiolog", "neurosci", "psychiatry", "psycholog",
    "immunolog", "microbiolog", "molecular biology", "genom", "genetics",
    "biochem", "cell biology", "ecology", "zoolog", "botan", "marine biology",
    "cetacean", "agronom", "epidemiolog", "public health", "physiotherapy",
    "literature", "linguistic", "philosophy", "theolog", "divinity",
    "classics", "archaeolog", "anthropolog", "sociolog", "criminolog",
    "social work", "fine art", "music", "theatre", "theater", "drama", "dance",
    "film studies", "media studies", "journalism",
    "accounting", "marketing", "human resource", "tourism", "hospitality",
    "criminal law", "family law", "politics", "international relations",
    "pure mathematics", "astronom", "particle physics", "quantum",
    "organic chemistry", "food science", "sport science", "nutrition",
    "early childhood", "primary education", "teacher education",
    "librarian", "admissions", "student recruitment", "development officer",
    "fundraising", "receptionist", "catering", "cleaner", "porter", "caretaker",
    "counsel", "chaplain", "veterinar",
]

# ---------------------------------------------------------------------------
# Role model - how well each kind of post fits his career stage
# ---------------------------------------------------------------------------
# Checked in order; the first pattern found in the title wins.
ROLE_PATTERNS = [
    ("phd", "PhD position", [
        "phd student", "phd position", "phd scholarship", "phd candidate",
        "doctoral student", "doctoral candidate", "phd fellowship",
        "phd researcher", "graduate assistant", "phd studentship", "doctoral position",
    ], 0.05),
    ("chair", "Chair / Full Professor", [
        "chair of", "chair in", "full professor", "professorial chair",
        "head of school", "head of department", "dean of", "dean,", "dean ",
        "director of school", "distinguished professor", "university professorship",
        "w3 professor", "vice president", "provost", "pro vice-chancellor",
    ], 0.38),
    ("associate", "Associate Professor / Senior Lecturer", [
        "associate professor", "senior lecturer", "reader in", "reader,",
        "principal lecturer", "w2 professor", "associate teaching professor",
    ], 0.80),
    ("assistant", "Assistant Professor / Lecturer", [
        "assistant professor", "asst. professor", "asst professor", "lecturer",
        "tenure-track", "tenure track", "faculty position", "faculty positions",
        "academic position", "teaching fellow", "assistant teaching professor",
        "clinical faculty", "adjunct faculty", "instructor", "junior professor",
        "professor of", "professor in",
    ], 1.00),
    ("fellowship", "Fellowship", [
        "fellowship", "marie sk", "marie curie", "msca", "early career fellow",
        "junior research fellow", "independent fellow", "career development fellow",
        "leverhulme", "newton fellow", "banting", "humboldt", "royal society fellow",
    ], 0.95),
    ("postdoc", "Postdoc / Research Fellow", [
        "postdoc", "post-doc", "post doc", "postdoctoral", "research fellow",
        "research associate", "research scientist", "research officer",
        "senior researcher", "researcher in", "scientific staff",
        "wissenschaftliche", "research assistant professor",
    ], 0.88),
]
DEFAULT_ROLE = ("other", "Other / Support", 0.18)

# Roles he is not looking for - hidden by default in the UI.
LOW_INTEREST_ROLES = {"phd", "other"}

# Contract-quality modifiers applied on top of role fit. A candidate with 50
# journal articles and an h-index of 21 is aiming at permanent, research-active
# posts, so casual teaching cover is discounted even when the subject is perfect.
ROLE_DOWNGRADES = [
    (["adjunct", "part-time", "part time", "sessional", "casual",
      "hourly", "temporary faculty", "faculty pool", "temporary lecturer",
      "vocational", "community college", "technical college",
      "substitute", "cover teacher"], 0.45, "casual or adjunct contract"),
    (["professor of practice", "practice professor", "teaching-only",
      "teaching only", "instructor pool", "clinical faculty",
      "assistant teaching professor", "teaching fellow"], 0.68,
     "teaching-focused post"),
    (["fixed-term", "fixed term", "maternity cover", "secondment",
      "12 month", "one year", "1-year", "visiting"], 0.85, "fixed-term post"),
]

ROLE_UPGRADES = [
    (["tenure-track", "tenure track", "tenured", "permanent", "continuing",
      "open rank", "ongoing"], 1.08, "permanent or tenure-track"),
    (["research chair", "research-intensive", "research active",
      "phd supervision", "doctoral supervision", "grant capture",
      "research group", "start-up package", "startup package"], 1.04,
     "research-active post"),
]

# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
TARGET_COUNTRIES = {
    "United States": ["united states", "usa", "u.s.a", " u.s.", "alabama", "alaska",
                      "arizona", "arkansas", "california", "colorado", "connecticut",
                      "delaware", "florida", "georgia, us", "hawaii", "idaho",
                      "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
                      "maine", "maryland", "massachusetts", "michigan", "minnesota",
                      "mississippi", "missouri", "montana", "nebraska", "nevada",
                      "new hampshire", "new jersey", "new mexico", "new york",
                      "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
                      "pennsylvania", "rhode island", "south carolina", "south dakota",
                      "tennessee", "texas", "utah", "vermont", "virginia",
                      "washington", "west virginia", "wisconsin", "wyoming"],
    "United Kingdom": ["united kingdom", "england", "scotland", "wales",
                       "northern ireland", "london", "manchester", "birmingham",
                       "leeds", "glasgow", "edinburgh", "cardiff", "belfast",
                       "sheffield", "nottingham", "bristol", "liverpool",
                       "newcastle upon tyne", "southampton", "coventry", "leicester",
                       "loughborough", "cambridge", "oxford", "reading", "surrey",
                       "exeter", "bath", "aberdeen", "dundee", "swansea", "salford",
                       "hull", "york", "lancaster", "durham", "warwick", "brighton",
                       "portsmouth", "plymouth", "stirling", "aberystwyth"],
    "Canada": ["canada", "ontario", "quebec", "alberta", "british columbia",
               "toronto", "montreal", "vancouver", "calgary", "ottawa", "edmonton",
               "waterloo", "halifax", "saskatchewan", "manitoba", "winnipeg",
               "hamilton, on", "kingston, on", "victoria, bc", "newfoundland"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane", "perth",
                  "adelaide", "canberra", "queensland", "new south wales",
                  "wollongong", "tasmania", "darwin", "gold coast", "geelong"],
    "New Zealand": ["new zealand", "auckland", "wellington", "christchurch",
                    "canterbury", "otago", "dunedin", "waikato", "palmerston north"],
    "Ireland": ["ireland", "dublin", "cork", "galway", "limerick", "maynooth"],
    "Germany": ["germany", "deutschland", "berlin", "munich", "hamburg", "aachen",
                "stuttgart", "dresden", "karlsruhe", "darmstadt", "bochum",
                "hannover", "cologne", "leipzig", "freiburg", "bonn", "braunschweig",
                "kaiserslautern", "weimar", "stuttgart"],
    "Netherlands": ["netherlands", "delft", "amsterdam", "eindhoven", "utrecht",
                    "twente", "wageningen", "rotterdam", "groningen", "leiden"],
    "Switzerland": ["switzerland", "zurich", "lausanne", "geneva", "bern", "basel",
                    "eth zurich", "epfl", "lugano"],
    "Sweden": ["sweden", "stockholm", "gothenburg", "lund", "uppsala", "chalmers",
               "kth royal", "linkoping", "lulea"],
    "Norway": ["norway", "oslo", "trondheim", "bergen", "ntnu", "stavanger", "tromso"],
    "Denmark": ["denmark", "copenhagen", "aarhus", "aalborg", "lyngby",
                "technical university of denmark"],
    "Finland": ["finland", "helsinki", "espoo", "aalto", "tampere", "oulu", "turku"],
    "Belgium": ["belgium", "leuven", "ghent", "brussels", "antwerp", "liege"],
    "Austria": ["austria", "vienna", "graz", "innsbruck", "linz", "salzburg"],
    "France": ["france", "paris", "lyon", "grenoble", "toulouse", "marseille",
               "nantes", "lille", "bordeaux", "strasbourg", "montpellier", "rennes"],
    "Spain": ["spain", "madrid", "barcelona", "valencia", "seville", "sevilla",
              "granada", "bilbao", "zaragoza", "catalonia", "canaria"],
    "Italy": ["italy", "milan", "milano", "rome", "roma", "turin", "torino",
              "bologna", "padua", "padova", "naples", "florence", "genoa", "pisa"],
    "Portugal": ["portugal", "lisbon", "lisboa", "porto", "coimbra", "aveiro", "braga"],
    "Poland": ["poland", "warsaw", "krakow", "wroclaw", "gdansk", "poznan"],
    "Czechia": ["czech", "prague", "praha", "brno", "ostrava"],
    "Greece": ["greece", "athens", "thessaloniki", "patras", "crete"],
    "Luxembourg": ["luxembourg"],
    "Iceland": ["iceland", "reykjavik"],
    "Estonia": ["estonia", "tallinn", "tartu"],
    "Slovenia": ["slovenia", "ljubljana", "maribor"],
    "Romania": ["romania", "bucharest", "cluj", "timisoara"],
    "Hungary": ["hungary", "budapest", "debrecen"],
    "Cyprus": ["cyprus", "nicosia", "limassol"],
    "Malta": ["malta"],
}

# Not requested, but these post relevant roles. They score at a discount.
SECONDARY_COUNTRIES = {
    "UAE": ["united arab emirates", "abu dhabi", "dubai", "sharjah"],
    "Saudi Arabia": ["saudi", "kaust", "riyadh", "dhahran", "jeddah", "thuwal"],
    "Qatar": ["qatar", "doha"],
    "Singapore": ["singapore", "nanyang technological"],
    "Hong Kong": ["hong kong", "kowloon", "polytechnic university of hong"],
    "China": ["china", "beijing", "shanghai", "shenzhen", "hangzhou", "wuhan",
              "tsinghua", "westlake university", "zhejiang", "guangzhou", "chengdu"],
    "Japan": ["japan", "tokyo", "kyoto", "osaka", "okinawa", "sendai"],
    "South Korea": ["korea", "seoul", "kaist", "busan", "daejeon"],
    "Israel": ["israel", "tel aviv", "haifa", "technion", "jerusalem"],
    "South Africa": ["south africa", "cape town", "johannesburg", "pretoria",
                     "stellenbosch", "durban"],
}

COUNTRY_FIT = {"target": 1.00, "secondary": 0.55, "unknown": 0.72}

# ---------------------------------------------------------------------------
# Score composition
# ---------------------------------------------------------------------------
WEIGHTS = {
    "topic": 0.55,      # subject-matter alignment with his publication record
    "role": 0.25,       # seniority / post type fit for an early-career academic
    "country": 0.12,    # is it in a country he named
    "freshness": 0.08,  # recently posted and deadline not already gone
}

TOPIC_SATURATION = 34.0   # raw topic score at which topic fit reaches 1.0
PLAUSIBILITY_FLOOR = 6.0  # below this raw topic score the post is not his field

# Curated fellowship schemes are hand-picked for eligibility, so they are given
# this subject-fit floor instead of being scored on their (discipline-neutral)
# wording. Raise it to push fellowships up the list, lower it to push them down.
CURATED_TOPIC_FLOOR = 0.72
