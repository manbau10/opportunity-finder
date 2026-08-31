# -*- coding: utf-8 -*-
"""
Curated early-career fellowship schemes.

Named fellowships are announced on funder websites, not job boards, so the four
scraped sources almost never surface them. This module carries a hand-kept
register of the major recurring schemes an early-career infrastructure or civil
engineering academic can apply to in the target regions.

Deliberately, no scheme here claims a specific closing date. Rounds move every
year, and inventing a date would be worse than leaving it out; each entry states
the month the call usually opens and links to the official page, which is the
only reliable source for the current round.

To add a scheme, append to SCHEMES. Fields:
    name, funder, country, window (when the call usually runs), url, about
"""

from __future__ import annotations

from .base import make_id

NAME = "Fellowship register"

SCHEMES = [
    # ---------------------------------------------------------------- Europe
    dict(name="Marie Sklodowska-Curie Postdoctoral Fellowship (MSCA-PF)",
         funder="European Commission, Horizon Europe", country="Europe-wide",
         window="call usually opens April, closes September",
         url="https://marie-sklodowska-curie-actions.ec.europa.eu/actions/postdoctoral-fellowships",
         about="Two-year individual postdoctoral fellowship at any European host "
               "institution, plus a Global Fellowship option. Strongly suited to "
               "infrastructure asset management, water distribution network and "
               "AI-for-civil-engineering projects with a named supervisor."),
    dict(name="ERC Starting Grant",
         funder="European Research Council", country="Europe-wide",
         window="call usually opens July, closes October",
         url="https://erc.europa.eu/apply-grant/starting-grant",
         about="Up to EUR 1.5 million over five years for researchers 2-7 years "
               "after the PhD to build an independent group. Requires a European "
               "host institution."),
    dict(name="Humboldt Research Fellowship for Postdoctoral Researchers",
         funder="Alexander von Humboldt Foundation", country="Germany",
         window="applications accepted year-round, reviewed three times a year",
         url="https://www.humboldt-foundation.de/en/apply/sponsorship-programmes/humboldt-research-fellowship",
         about="Six to twenty-four months of research at a German institution for "
               "researchers within four years of the doctorate. Open to all "
               "disciplines including civil and environmental engineering."),
    dict(name="NWO Veni",
         funder="Dutch Research Council (NWO)", country="Netherlands",
         window="call usually runs autumn to winter",
         url="https://www.nwo.nl/en/researchprogrammes/nwo-talent-programme/veni",
         about="Up to EUR 320,000 over three years for researchers within three "
               "years of the PhD at a Dutch institution. Delft, Twente, Eindhoven "
               "and Wageningen all host strong water and infrastructure groups."),
    dict(name="ETH Zurich Postdoctoral Fellowships",
         funder="ETH Zurich", country="Switzerland",
         window="two calls a year, usually March and September",
         url="https://ethz.ch/en/research/research-promotion/eth-fellowships.html",
         about="Two-year fellowship for researchers moving to ETH Zurich. "
               "Directly relevant given the six-month academic-guest period at "
               "the Institute of Construction and Infrastructure Management."),
    dict(name="SNSF Postdoc.Mobility and Ambizione",
         funder="Swiss National Science Foundation", country="Switzerland",
         window="Postdoc.Mobility twice a year; Ambizione usually November",
         url="https://www.snf.ch/en/N18L3oGWomTSSGkF/funding/careers",
         about="Postdoc.Mobility funds research abroad; Ambizione funds an "
               "independent project at a Swiss institution for early-career "
               "researchers."),
    dict(name="FWO Junior Postdoctoral Fellowship",
         funder="Research Foundation Flanders", country="Belgium",
         window="call usually closes December",
         url="https://www.fwo.be/en/fellowships-funding/postdoctoral-fellowships/junior-postdoctoral-fellowship/",
         about="Three-year fellowship at a Flemish university (KU Leuven, Ghent, "
               "Antwerp) for researchers within three years of the doctorate."),
    dict(name="FWF ESPRIT Programme",
         funder="Austrian Science Fund (FWF)", country="Austria",
         window="applications accepted continuously",
         url="https://www.fwf.ac.at/en/research-funding/fwf-programmes/esprit-programme",
         about="Three-year postdoctoral programme at an Austrian institution, "
               "open to all fields including construction and civil engineering."),
    dict(name="Carlsberg Foundation Internationalisation Fellowship",
         funder="Carlsberg Foundation", country="Denmark",
         window="call usually closes October",
         url="https://www.carlsbergfondet.dk/en/",
         about="Fellowships supporting researchers moving to or from Danish "
               "institutions; DTU and Aalborg host major construction and water "
               "engineering groups."),
    dict(name="Marie Curie / EURAXESS national fellowship portals",
         funder="EURAXESS", country="Europe-wide",
         window="rolling",
         url="https://euraxess.ec.europa.eu/funding/search",
         about="Aggregated European funding and fellowship calls, filterable by "
               "country and research field. Worth a monthly sweep for civil "
               "engineering and water science calls."),

    # ------------------------------------------------------------ United Kingdom
    dict(name="UKRI Future Leaders Fellowship",
         funder="UK Research and Innovation", country="United Kingdom",
         window="rounds usually announced once or twice a year",
         url="https://www.ukri.org/what-we-do/developing-people-and-skills/future-leaders-fellowships/",
         about="Four to seven years of funding to establish an independent group "
               "at a UK institution. Explicitly welcomes engineering and "
               "infrastructure research with industry partnership - a good fit "
               "for water utility and asset management collaboration."),
    dict(name="Royal Academy of Engineering Research Fellowship",
         funder="Royal Academy of Engineering", country="United Kingdom",
         window="call usually opens September",
         url="https://raeng.org.uk/programmes-and-prizes/programmes/support-for-research/research-fellowships",
         about="Five-year fellowship for outstanding early-career engineering "
               "researchers within four years of the PhD, at a UK university. "
               "One of the strongest routes into a UK engineering faculty post."),
    dict(name="Leverhulme Early Career Fellowship",
         funder="Leverhulme Trust", country="United Kingdom",
         window="call usually opens January, closes late February",
         url="https://www.leverhulme.ac.uk/early-career-fellowships",
         about="Three-year fellowship for researchers within four years of the "
               "doctorate, with the UK host contributing part of the salary. "
               "Requires early contact with the host department."),
    dict(name="Royal Society University Research Fellowship",
         funder="The Royal Society", country="United Kingdom",
         window="call usually opens July, closes September",
         url="https://royalsociety.org/grants/university-research/",
         about="Eight-year fellowship for outstanding early-career scientists "
               "and engineers to build an independent research programme in the UK."),
    dict(name="Newton International Fellowship",
         funder="The Royal Society / British Academy", country="United Kingdom",
         window="call usually opens autumn",
         url="https://royalsociety.org/grants/newton-international/",
         about="Two-year fellowship bringing early-career researchers based "
               "outside the UK to a UK institution. Aimed at researchers within "
               "seven years of the PhD."),
    dict(name="EPSRC Postdoctoral Fellowship",
         funder="Engineering and Physical Sciences Research Council",
         country="United Kingdom", window="open call, rolling",
         url="https://www.ukri.org/opportunity/epsrc-postdoctoral-fellowship/",
         about="Fellowship in EPSRC's remit, which covers construction, "
               "infrastructure, water engineering and engineering AI."),

    # -------------------------------------------------------------- Canada
    dict(name="Banting Postdoctoral Fellowship",
         funder="Government of Canada", country="Canada",
         window="call usually opens summer, closes September",
         url="https://banting.fellowships-bourses.gc.ca/en/home-accueil.html",
         about="CAD 70,000 a year for two years, Canada's flagship postdoctoral "
               "award. Engineering applications go through NSERC; requires an "
               "endorsed Canadian host institution well before the deadline."),
    dict(name="NSERC Postdoctoral Fellowship",
         funder="Natural Sciences and Engineering Research Council",
         country="Canada", window="call usually closes October",
         url="https://www.nserc-crsng.gc.ca/students-etudiants/pd-np/pdf-bp_eng.asp",
         about="Two-year fellowship in the natural sciences and engineering, "
               "held at a Canadian or foreign institution."),
    dict(name="Canada Research Chairs (Tier 2)",
         funder="Government of Canada", country="Canada",
         window="nominated by universities, advertised year-round",
         url="https://www.chairs-chaires.gc.ca/home-accueil-eng.aspx",
         about="Five-year chair for exceptional emerging researchers, normally "
               "attached to a tenure-track offer. Watch Canadian faculty adverts "
               "that mention a Tier 2 CRC - they are effectively a fellowship "
               "plus a permanent post."),

    # ------------------------------------------------------- Australia / NZ
    dict(name="ARC Discovery Early Career Researcher Award (DECRA)",
         funder="Australian Research Council", country="Australia",
         window="call usually opens mid-year, closes around March for the next round",
         url="https://www.arc.gov.au/funding-research/funding-schemes/discovery-program/discovery-early-career-researcher-award-decra",
         about="Three years of salary and project funding for researchers within "
               "five years of the PhD at an Australian university. Highly "
               "competitive and the standard route to an Australian faculty post."),
    dict(name="Australian Research Council Future Fellowship",
         funder="Australian Research Council", country="Australia",
         window="annual round",
         url="https://www.arc.gov.au/funding-research/funding-schemes/discovery-program/future-fellowships",
         about="Four-year fellowship for mid-career researchers, typically 5-15 "
               "years post-PhD. Worth tracking for a later application."),
    dict(name="Rutherford Discovery Fellowship",
         funder="Royal Society Te Aparangi", country="New Zealand",
         window="call usually opens early in the year",
         url="https://www.royalsociety.org.nz/what-we-do/funds-and-opportunities/rutherford-discovery-fellowships/",
         about="Five-year fellowship for early- to mid-career researchers at a "
               "New Zealand institution."),
    dict(name="Marsden Fund Fast-Start",
         funder="Royal Society Te Aparangi", country="New Zealand",
         window="preliminary proposals usually due February",
         url="https://www.royalsociety.org.nz/what-we-do/funds-and-opportunities/marsden-fund/",
         about="Three-year grant for researchers within seven years of the PhD "
               "at a New Zealand institution, including engineering."),

    # -------------------------------------------------------- United States
    dict(name="NSF CAREER Award",
         funder="US National Science Foundation", country="United States",
         window="annual deadline, usually July",
         url="https://www.nsf.gov/funding/opportunities/faculty-early-career-development-program-career",
         about="Five-year award for untenured US faculty, covering the Civil, "
               "Mechanical and Manufacturing Innovation and Environmental "
               "Engineering programmes. Requires a tenure-track post first, so "
               "treat it as the year-one target after landing a US position."),
    dict(name="Schmidt Science Fellows",
         funder="Schmidt Futures", country="United States / global",
         window="nominations usually open mid-year",
         url="https://schmidtsciencefellows.org/",
         about="One to two years of interdisciplinary postdoctoral work at a "
               "leading institution worldwide. Requires nomination by a "
               "participating university."),
    dict(name="Ford Foundation / NAS Postdoctoral Fellowship",
         funder="US National Academies", country="United States",
         window="call usually closes December",
         url="https://www.nationalacademies.org/our-work/ford-foundation-fellowships",
         about="Postdoctoral fellowship supporting researchers committed to "
               "diversity in US higher education. Check the citizenship and "
               "residency conditions before investing time."),
]


def fetch(log=print) -> list[dict]:
    out = []
    for scheme in SCHEMES:
        key = make_id("fellowship", scheme["url"] + "|" + scheme["name"])
        out.append({
            "id": key,
            "source": NAME,
            "source_key": "fellowships",
            "title": scheme["name"],
            "org": scheme["funder"],
            "location": scheme["country"],
            "url": scheme["url"],
            "description": ("Recurring scheme - %s. No fixed deadline is shown "
                            "here on purpose: rounds move each year, so open the "
                            "link for the current call. %s"
                            % (scheme["window"], scheme["about"])),
            "posted": "",
            "deadline": "",
            "query": "curated fellowship register",
            "curated": True,
            "extra_flags": ["recurring scheme - check the link for this year's round"],
        })
    log("  fellowships: %d curated schemes" % len(out))
    return out
