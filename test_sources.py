"""Offline checks for the job-source adapters, search phrases, locating and matching.

No network is used: every adapter is fed a small copy of the page or API answer it
reads in production. `python check_sources.py` is the live counterpart.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "integration-test-secret-not-for-production")
os.environ["OPPFINDER_DATA_DIR"] = tempfile.mkdtemp(prefix="oppfinder-test-src-")

from finder import industry_sources as ind
from finder import matching, profiles, queries, research
from finder.domains import classify
from finder.scoring import locate
from finder.sources import academictransfer, ajo, euraxess, madgex

RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Job Search RSS</title>
<item><title>Lamar University: Instructor, Civil &amp; Environmental Engineering</title>
<description>

Lamar University:
Job SummaryThe Department of Civil and Environmental Engineering invites applications.
Beaumont, TX, TX
</description>
<link>https://careers.insidehighered.com/job/3561738/instructor-civil/?TrackID=11&amp;utm_source=rss</link>
<pubDate>Sun, 11 Oct 2026 04:00:00 -0500</pubDate></item>
<item><title>UNIVERSITY OF READING: Lecturer in Quantity Surveying</title>
<description>Reading, England</description>
<link>https://www.timeshighereducation.com/unijobs/listing/1/lecturer/</link></item>
</channel></rss>"""

AJO_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:ads="http://academicjobsonline.org/ads"><channel>
<item><title>Assistant Professor of Structural Engineering</title>
<link>https://academicjobsonline.org/ajo/Univ/Dept/33001?rss</link>
<description>Seeking a civil infrastructure researcher.</description>
<ads:univ>University of Ottawa</ads:univ><ads:city>Ottawa</ads:city>
<ads:state>Ontario</ads:state><ads:country>CA</ads:country>
<ads:disciplines>Civil Engineering</ads:disciplines></item>
<item><title>Postdoctoral Researcher in Cosmology</title>
<link>https://academicjobsonline.org/ajo/Univ/Dept/33002?rss</link>
<description>Dark matter.</description><ads:univ>Somewhere</ads:univ>
<ads:disciplines>Physics</ads:disciplines></item></channel></rss>"""

AT_HTML = """<ul><li><article>
<a href="/en/jobs/364872/postdoc-position-public-toilet-governance/"></a>
<div><h3>Postdoc position: infrastructure governance</h3>
<p>Study social infrastructure and inclusive cities.</p></div>
<div>Deadline | 31 Jan '27 | Published | 15 Oct '26 | Leiden | Leiden University</div>
</article></li></ul>"""

EURAXESS_HTML = """<div class="ecl-content-item"><div class="ecl-content-block">
<div>University of Stavanger</div><div>Posted on: 20 October 2026</div>
<h3 class="ecl-content-block__title"><a href="/jobs/474225">Postdoctoral Fellow in Water Infrastructure</a></h3>
<div>The fellow will study water infrastructure resilience and pipe failure prediction in cities.</div>
</div></div>"""


class MadgexTest(unittest.TestCase):
    def test_feed_is_parsed_and_tracking_removed(self):
        items = madgex.parse_feed(RSS.encode(), "Inside Higher Ed", "insidehighered", "q", "United States")
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first["org"], "Lamar University")
        self.assertEqual(first["title"].strip(), "Instructor, Civil & Environmental Engineering")
        self.assertEqual(first["location"], "Beaumont, TX, TX")
        self.assertNotIn("TrackID", first["url"])
        self.assertEqual(first["country_hint"], "United States")
        self.assertEqual(items[1]["org"], "University Of Reading")

    def test_same_advert_keeps_one_identity_across_tracking_variants(self):
        a = madgex.parse_feed(RSS.encode(), "X", "x", "q")[0]["id"]
        b = madgex.parse_feed(RSS.replace("TrackID=11", "TrackID=99").encode(), "X", "x", "q")[0]["id"]
        self.assertEqual(a, b)


class AcademicSourceTest(unittest.TestCase):
    def test_ajo_keeps_only_posts_in_the_users_subjects(self):
        items = ajo.parse(AJO_RSS.encode(), {"civil engineering", "infrastructure"})
        self.assertEqual([i["title"] for i in items], ["Assistant Professor of Structural Engineering"])
        item = items[0]
        self.assertEqual(item["org"], "University of Ottawa")
        self.assertIn("Ottawa", item["location"])
        self.assertEqual(item["country_hint"], "Canada")
        self.assertFalse(item["url"].endswith("?rss"))

    def test_academictransfer_card(self):
        items = academictransfer.parse(AT_HTML)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["org"], "Leiden University")
        self.assertIn("Leiden", items[0]["location"])
        self.assertTrue(items[0]["url"].startswith("https://www.academictransfer.com/en/jobs/364872/"))

    def test_euraxess_card_org_is_the_line_before_posted_on(self):
        items, seen = euraxess.parse(EURAXESS_HTML, {"water infrastructure"})
        self.assertEqual(seen, 1)
        self.assertEqual(items[0]["org"], "University of Stavanger")
        self.assertEqual(items[0]["posted"], "20 October 2026")
        items, _ = euraxess.parse(EURAXESS_HTML, {"nursing"})
        self.assertEqual(items, [])


class IndustrySourceTest(unittest.TestCase):
    def test_title_matching_needs_the_distinctive_word(self):
        wanted = ["civil engineer", "project manager"]
        self.assertTrue(ind.title_matches("Senior Civil Engineer (BIM)", wanted))
        self.assertTrue(ind.title_matches("IT Project Manager", wanted))
        self.assertFalse(ind.title_matches("Software Engineer", wanted))
        self.assertFalse(ind.title_matches("Account Executive", wanted))

    def test_explicit_country_overrides_guessing(self):
        item = ind.make_item("S", "k", "Engineer", "Org", "Lagos", "https://x/1", "text",
                             country="Nigeria")
        self.assertEqual(item["country"], "Nigeria")
        self.assertEqual(item["career_track"], "industry")
        self.assertEqual(len(item["id"]), 20)

    def test_sweden_api_row(self):
        payload = {"hits": [{
            "headline": "Civil Project Engineer", "employer": {"name": "BTR AB"},
            "workplace_address": {"municipality": "Stockholm", "region": "Stockholms län"},
            "webpage_url": "https://arbetsformedlingen.se/platsbanken/annonser/1",
            "description": {"text": "Design bridges."},
            "publication_date": "2026-09-21T00:00:00", "application_deadline": "2026-12-15T23:59:59"}]}
        with patch.object(ind, "get_json", return_value=payload):
            items = ind.fetch_sweden(["civil engineer"], lambda *_: None)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["country"], "Sweden")
        self.assertEqual(items[0]["deadline"], "2026-12-15")
        self.assertEqual(items[0]["org"], "BTR AB")

    def test_switzerland_api_row(self):
        payload = {"documents": [{
            "title": "Bauingenieur", "company_name": "ERNE AG", "place": "Stein",
            "preview": "Bau", "publication_date": "2026-10-12T00:00:00+02:00",
            "_links": {"detail_en": {"href": "https://www.jobs.ch/en/vacancies/detail/abc/"}}}]}
        with patch.object(ind, "get_json", return_value=payload):
            items = ind.fetch_switzerland(["civil engineer"], lambda *_: None)
        self.assertEqual(items[0]["country"], "Switzerland")
        self.assertEqual(items[0]["posted"], "2026-10-12")

    def test_reed_embedded_json(self):
        class Page:
            text = ('<script id="__NEXT_DATA__" type="application/json">'
                    '{"props":{"pageProps":{"searchResults":{"jobs":[{"jobDetail":{'
                    '"jobId":57352635,"jobTitle":"Civil Engineer","displayLocationName":"Leeds",'
                    '"countyLocation":"Yorkshire","displayDate":"2026-09-16T10:28:33",'
                    '"expiryDate":"2026-10-28T23:55:00","jobDescriptionSnippet":"Design"},'
                    '"profileName":"Matchtech","url":"/jobs/civil-engineer/57352635"}]}}}}'
                    '</script>')
        with patch.object(ind, "get", return_value=Page()):
            items = ind.fetch_reed_uk(["civil engineer"], lambda *_: None)
        self.assertEqual(items[0]["org"], "Matchtech")
        self.assertEqual(items[0]["deadline"], "2026-10-28")
        self.assertEqual(items[0]["url"], "https://www.reed.co.uk/jobs/civil-engineer/57352635")
        self.assertEqual(items[0]["country"], "United Kingdom")

    def test_job_bank_canada_article(self):
        class Page:
            text = ('<article id="article-49924863"><a class="resultJobItem" href="/x">'
                    '<h3 class="title"><span class="noctitle">civil engineer</span></h3>'
                    '<ul><li class="date">July 17, 2026</li><li class="business">EXL Engineering</li>'
                    '<li class="location"><span class="wb-inv">Location</span> Kelowna (BC)</li></ul>'
                    '</a></article>')
        with patch.object(ind, "get", return_value=Page()):
            items = ind.fetch_canada(["civil engineer"], lambda *_: None)
        self.assertEqual(items[0]["url"], "https://www.jobbank.gc.ca/jobsearch/jobposting/49924863")
        self.assertEqual(items[0]["org"], "EXL Engineering")
        self.assertIn("Kelowna", items[0]["location"])
        self.assertEqual(items[0]["country"], "Canada")
        self.assertEqual(items[0]["posted"], "2026-07-17")

    def test_governmentjobs_row(self):
        class Page:
            text = ('<ul><li class="job-item"><div class="job-item-container">'
                    '<div class="row-fluid job-tile-header"><h3><a href="/jobs/5517177-0/civil-engineer">'
                    'Civil Engineer</a></h3></div><ul><li>City of Irving</li><li>Irving, TX</li>'
                    '<li>$88,656 Annually</li></ul></div></li></ul>')
        with patch.object(ind, "get", return_value=Page()):
            items = ind.fetch_usa_government(["civil engineer"], lambda *_: None)
        self.assertEqual(items[0]["org"], "City of Irving")
        self.assertEqual(items[0]["country"], "United States")

    def test_jobberman_family_cards(self):
        class Page:
            text = ('<div class="container"><div class="card">'
                    '<a href="https://www.jobberman.com/listings/project-engineer-5pgp6g?x=1">Project Engineer</a>'
                    '<p>Topek Engineering Ltd</p><p>Lagos</p><p>Full Time</p></div></div>')
        with patch.object(ind, "get", return_value=Page()):
            items = ind.fetch_nigeria(["civil engineer"], lambda *_: None)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["country"], "Nigeria")
        self.assertEqual(items[0]["url"], "https://www.jobberman.com/listings/project-engineer-5pgp6g")

    def test_one_dead_source_does_not_stop_the_others(self):
        def boom(titles, log):
            raise RuntimeError("site changed")
        good = [("a", "A", "X", lambda titles, log: [ind.make_item("A", "a", "Civil Engineer", "O", "L", "https://u/1", "d")]),
                ("b", "B", "Y", boom)]
        from finder import industry
        with patch.object(ind, "SOURCES", good), patch.object(industry, "_wants_nhs", return_value=False), \
             patch.object(industry, "_fetch_profile_web_jobs", return_value=[]), \
             patch.object(industry.industry_sources, "SOURCES", good):
            found = industry.fetch(lambda *_: None)
        self.assertEqual([i["title"] for i in found], ["Civil Engineer"])


class LocateTest(unittest.TestCase):
    def test_whole_words_only(self):
        self.assertEqual(locate("I was reading about work")[0], "")
        self.assertEqual(locate("University of Reading")[0], "United Kingdom")
        self.assertEqual(locate("Lagos")[0], "Nigeria")

    def test_state_and_province_codes(self):
        self.assertEqual(locate("Austin, TX")[0], "United States")
        self.assertEqual(locate("Birmingham, AL")[0], "United States")
        self.assertEqual(locate("Calgary (AB)")[0], "Canada")
        self.assertEqual(locate("Leeds, West Yorkshire")[0], "United Kingdom")


class ProfileAndQueryTest(unittest.TestCase):
    CV = ("Dr Jane Okafor\nSenior Lecturer in Construction Management\n"
          "Research interests: water infrastructure, construction management, digital twin.\n" * 6
          + "Okafor, J., Zayed, T. (2024). Water infrastructure planning. https://doi.org/10.1000/xyz\n" * 4
          + "Site Engineer (03/2019-01/2020)\nTeaching Assistant (2018)\nPhD in Civil Engineering\n")

    def test_keywords_are_subjects_not_names_or_noise(self):
        keywords = profiles.build_profile(self.CV, "industry")["keywords"]
        self.assertIn("water infrastructure", keywords)
        self.assertIn("construction management", keywords)
        for junk in ("okafor", "zayed", "https", "doi.org", "for", "the"):
            self.assertNotIn(junk, keywords)

    def test_job_titles_are_clean_and_exclude_student_roles(self):
        titles = profiles.build_profile(self.CV, "industry")["target_titles"]
        self.assertIn("Site Engineer", titles)
        self.assertFalse(any("(" in t or "2019" in t for t in titles))
        self.assertNotIn("Teaching Assistant", titles)

    def test_queries_follow_the_uploaded_cv(self):
        from finder import auth, store
        user, error = auth.register_user("Query Tester", "queries@example.invalid", "a-long-test-password-1")
        self.assertIsNone(error)
        profiles.save_profile(user["id"], "academic", "cv.txt", self.CV.encode())
        profiles.save_profile(user["id"], "industry", "cv.txt", self.CV.encode())
        academic = queries.academic_queries()
        self.assertIn("water infrastructure", academic)
        self.assertTrue(any(q.startswith("postdoctoral ") for q in academic))
        self.assertTrue(any("site engineer" == t for t in queries.industry_titles()))
        terms = queries.relevance_terms()
        self.assertTrue(queries.looks_relevant("Postdoc on water infrastructure resilience", terms))
        self.assertFalse(queries.looks_relevant("Postdoc in marine ecology and fisheries", terms))


class MatchingTest(unittest.TestCase):
    PROFILE = {"kind": "academic", "cv_text": "construction management civil engineering " * 20,
               "profile": {"keywords": ["construction management", "civil engineering"],
                           "target_titles": ["assistant professor", "lecturer"],
                           "primary_domain": "construction", "degree": "PhD",
                           "preferred_locations": []}}

    def job(self, title, **extra):
        return {"title": title, "org": "Uni", "description":
                "Construction management and civil engineering research and teaching.",
                "location": "Leeds", "country": "United Kingdom", "days_left": 40, **extra}

    def test_adjunct_and_vocational_posts_rank_below_tenure_track(self):
        main = matching.score_for_profile(self.job("Assistant Professor of Construction Management"), self.PROFILE)[0]
        adjunct = matching.score_for_profile(self.job("Adjunct Assistant Professor, Construction Management"), self.PROFILE)[0]
        self.assertGreater(main, adjunct + 5)

    def test_phd_studentship_suits_a_candidate_without_a_doctorate(self):
        studentship = self.job("PhD studentship in construction management")
        with_phd = matching.score_for_profile(studentship, self.PROFILE)[0]
        without = {**self.PROFILE, "profile": {**self.PROFILE["profile"], "degree": "Master's"}}
        self.assertGreater(matching.score_for_profile(studentship, without)[0], with_phd + 10)

    def test_closed_posts_are_capped(self):
        score = matching.score_for_profile(
            self.job("Assistant Professor of Construction Management", days_left=-3), self.PROFILE)[0]
        self.assertLessEqual(score, 25)

    def test_it_infrastructure_is_not_civil_infrastructure(self):
        self.assertNotIn("construction", classify("ML Infrastructure Engineer", title=True))
        self.assertIn("construction", classify("Infrastructure Project Manager", title=True))


class ResearchTest(unittest.TestCase):
    def test_subject_is_taken_from_the_title(self):
        self.assertEqual(research._subject_of("Assistant Professor of Construction Management"),
                         "Construction Management")
        self.assertEqual(research._subject_of("Postdoctoral Research Fellow - Water Infrastructure"),
                         "Water Infrastructure")
        self.assertEqual(research._subject_of("Senior Lecturer, Nursing (Adult)"), "Nursing")

    def test_queries_use_the_posts_own_subject(self):
        joined = " ".join(research._queries(
            {"org": "Univ X", "title": "Lecturer in Nursing", "department": ""}, "academic"))
        self.assertIn("Nursing", joined)
        self.assertNotIn("civil engineering", joined.lower())

    def test_official_site_rejects_a_look_alike(self):
        def fake(url, **params):
            if "wbsearchentities" in url or params.get("action") == "wbsearchentities":
                return {"search": [{"id": "Q1", "label": "Terras Energy", "description": "company"}]}
            raise AssertionError("must not fetch an entity that does not match the name")
        with patch.object(research, "_json", side_effect=fake):
            self.assertEqual(research.official_site("SB Energy"), {"website": "", "summary": None})

    def test_attachment_names_avoid_generic_link_text(self):
        name = research._attachment_name("here", "https://x.edu/files/person-specification.pdf", ".pdf")
        self.assertEqual(name, "person specification.pdf")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class StorageTest(unittest.TestCase):
    def test_short_listing_snippet_never_replaces_a_long_stored_advert(self):
        from finder import store
        item = ind.make_item("S", "k", "Civil Engineer", "O", "L", "https://u/keep", "x" * 5000)
        conn = store.connect()
        store.upsert_many(conn, [item])
        short = dict(item, description="short snippet")
        store.upsert_many(conn, [short])
        row = conn.execute("SELECT length(description) AS n FROM opportunities WHERE id=?",
                           (item["id"],)).fetchone()
        conn.close()
        self.assertEqual(row["n"], 5000)


class KeyedSourceTest(unittest.TestCase):
    def test_sources_switch_on_only_with_keys(self):
        with patch.dict(os.environ, {}, clear=False):
            for name in ("ADZUNA_APP_ID", "JOOBLE_API_KEY", "USAJOBS_API_KEY", "REED_API_KEY"):
                os.environ.pop(name, None)
            self.assertEqual(ind.keyed_sources(), [])
        with patch.dict(os.environ, {"JOOBLE_API_KEY": "k", "REED_API_KEY": "r"}):
            self.assertEqual([k for k, _ in ind.keyed_sources()], ["jooble", "uk_reed_api"])

    def test_usajobs_row(self):
        payload = {"SearchResult": {"SearchResultItems": [{"MatchedObjectDescriptor": {
            "PositionTitle": "Civil Engineer", "OrganizationName": "US Army Corps",
            "PositionLocationDisplay": "Seattle, Washington", "PositionURI": "https://www.usajobs.gov/job/1",
            "PublicationStartDate": "2026-10-01", "ApplicationCloseDate": "2026-11-01",
            "UserArea": {"Details": {"JobSummary": "Design flood works."}}}}]}}
        with patch.dict(os.environ, {"USAJOBS_API_KEY": "k", "USAJOBS_EMAIL": "a@b.c"}), \
             patch.object(ind, "get_json", return_value=payload):
            items = ind.fetch_usajobs(["civil engineer"], lambda *_: None)
        self.assertEqual(items[0]["deadline"], "2026-11-01")
        self.assertEqual(items[0]["country"], "United States")


class ManualJobTest(unittest.TestCase):
    def test_private_job_is_visible_only_to_its_owner(self):
        from finder import auth, manual_jobs, store
        a, _ = auth.register_user("Owner One", "owner1@example.invalid", "a-long-test-password-1")
        b, _ = auth.register_user("Owner Two", "owner2@example.invalid", "a-long-test-password-1")
        cv = ("Civil engineer and construction management researcher. Water infrastructure, BIM. " * 12).encode()
        for u in (a, b):
            profiles.save_profile(u["id"], "industry", "cv.txt", cv)
        text = "We seek a civil engineer for water infrastructure and construction management projects. " * 5
        with patch.object(manual_jobs, "prefill", return_value={}):
            job = manual_jobs.add_job(a["id"], "industry", {
                "url": "https://www.higheredjobs.com/details.cfm?JobCode=1", "title": "Civil Engineer",
                "org": "Some University", "description": text})
        matching.rebuild_matches(a["id"], "industry")
        matching.rebuild_matches(b["id"], "industry")
        conn = store.connect()
        mine = conn.execute("SELECT 1 FROM user_matches WHERE user_id=? AND opportunity_id=?", (a["id"], job["id"])).fetchone()
        theirs = conn.execute("SELECT 1 FROM user_matches WHERE user_id=? AND opportunity_id=?", (b["id"], job["id"])).fetchone()
        conn.close()
        self.assertIsNotNone(mine)
        self.assertIsNone(theirs)

    def test_blocked_site_without_text_asks_for_the_text(self):
        from finder import manual_jobs
        with patch.object(manual_jobs, "prefill", return_value={}):
            with self.assertRaises(ValueError) as ctx:
                manual_jobs.add_job("u", "industry", {"url": "https://x.example/job/1", "title": "T"})
        self.assertIn("Paste the advert text", str(ctx.exception))
        with self.assertRaises(ValueError):
            manual_jobs.add_job("u", "industry", {"url": "javascript:alert(1)"})


class AccountTest(unittest.TestCase):
    def test_export_delete_and_limits(self):
        from finder import account, auth, store
        u, _ = auth.register_user("Gone Soon", "gone@example.invalid", "a-long-test-password-1")
        profiles.save_profile(u["id"], "industry", "cv.txt", ("Civil engineer water infrastructure. " * 20).encode())
        data = account.export_data(u["id"])
        self.assertEqual(data["account"]["email"], "gone@example.invalid")
        self.assertEqual(len(data["cv_profiles"]), 1)
        self.assertFalse(account.delete_account(u["id"], "wrong password"))
        self.assertTrue(account.delete_account(u["id"], "a-long-test-password-1"))
        conn = store.connect()
        left = conn.execute("SELECT (SELECT COUNT(*) FROM users WHERE id=?) + "
                            "(SELECT COUNT(*) FROM user_profiles WHERE user_id=?) AS n",
                            (u["id"], u["id"])).fetchone()["n"]
        conn.close()
        self.assertEqual(left, 0)

    def test_rate_limiter(self):
        from finder.account import RateLimiter
        limiter = RateLimiter(limit=3, window=60)
        self.assertEqual([limiter.allow("a") for _ in range(4)], [True, True, True, False])
        self.assertTrue(limiter.allow("b"))


class InviteTest(unittest.TestCase):
    def test_invite_code_gates_sign_up(self):
        import re
        from app import app
        c = app.test_client()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', c.get("/register").get_data(as_text=True)).group(1)
        form = {"csrf_token": tok, "name": "Invited Person", "email": "inv@example.invalid",
                "password": "a-long-test-password-1", "accept_terms": "1"}
        with patch.dict(os.environ, {"INVITE_CODE": "friends-2026"}):
            self.assertIn(b"Invite code", c.get("/register").data)
            self.assertEqual(c.post("/register", data={**form, "invite_code": "nope"}).status_code, 200)
            self.assertEqual(c.post("/register", data={**form, "invite_code": "friends-2026"}).status_code, 302)
