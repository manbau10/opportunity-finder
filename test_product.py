"""Integration checks for account isolation and the commercial product flow."""

from __future__ import annotations

import base64
import io
import os
import unittest
import json
import zipfile
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "integration-test-secret-not-for-production")

from app import app
from finder import pipeline, store
from finder import application_pack

EMAILS = ("product-test-one@example.invalid", "product-test-two@example.invalid")
OPP_IDS = ("__product_academic__", "__product_industry__")


def cleanup_test_records() -> None:
    conn = store.connect()
    try:
        users = conn.execute("SELECT id FROM users WHERE email IN (?,?)", EMAILS).fetchall()
        for user in users:
            uid = user["id"]
            conn.execute("DELETE FROM application_packs WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM provider_configs WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM user_matches WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM user_profiles WHERE user_id=?", (uid,))
            conn.execute("DELETE FROM users WHERE id=?", (uid,))
        for opp_id in OPP_IDS:
            conn.execute("DELETE FROM opportunities WHERE id=?", (opp_id,))
        conn.commit()
    finally:
        conn.close()


def sample(opp_id: str, track: str) -> dict:
    return {
        "id": opp_id, "source": "Product self test", "source_key": "producttest",
        "title": ("Assistant Professor of Construction Management" if track == "academic"
                  else "Senior Infrastructure Project Manager"),
        "org": "Example Engineering Group", "department": "Civil and Infrastructure",
        "location": "Toronto, Canada", "country": "Canada", "country_tier": "target",
        "url": f"https://example.invalid/{opp_id}",
        "description": "Construction management, water infrastructure, digital twins, BIM and project delivery.",
        "posted": "2026-09-20", "deadline": "2026-12-31", "days_left": 100,
        "role_key": "assistant" if track == "academic" else "industry",
        "role_label": "Assistant Professor / Lecturer" if track == "academic" else "Industry role",
        "score": 50, "matched_terms": [], "flags": [], "positives": [], "breakdown": {},
        "query": "product test", "enriched": 1, "career_track": track, "status": "new",
    }


class ProductFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, SECRET_KEY=os.environ["SECRET_KEY"])
        cleanup_test_records()
        conn = store.connect()
        store.upsert_many(conn, [sample(OPP_IDS[0], "academic"), sample(OPP_IDS[1], "industry")])
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cleanup_test_records()

    def _register(self, email: str):
        client = app.test_client()
        client.get("/register")
        with client.session_transaction() as session:
            csrf = session["csrf"]
        response = client.post("/register", data={"name": "Product Test User", "email": email,
                               "password": "A-long-test-password-42", "csrf_token": csrf})
        self.assertEqual(response.status_code, 302)
        with client.session_transaction() as session:
            return client, session["csrf"], session["user_id"]

    def _upload(self, client, csrf: str, kind: str, text: str):
        response = client.post(f"/api/profiles/{kind}",
            data={"cv": (io.BytesIO(text.encode()), f"{kind}.txt")},
            headers={"X-CSRF-Token": csrf}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_end_to_end_account_isolation(self):
        one, csrf_one, uid_one = self._register(EMAILS[0])
        two, csrf_two, uid_two = self._register(EMAILS[1])
        cv_one = ("Civil engineer and construction management researcher. Water infrastructure, "
                  "digital twin, BIM, project delivery and asset management. " * 12)
        cv_two = ("Molecular biology laboratory specialist in genomics, proteins, cells and clinical assays. " * 14)
        self._upload(one, csrf_one, "academic", cv_one)
        self._upload(one, csrf_one, "industry", cv_one)
        self._upload(two, csrf_two, "academic", cv_two)

        self.assertEqual(one.get("/profile").status_code, 200)
        self.assertEqual(one.get("/settings").status_code, 200)
        was_running = pipeline.STATE["running"]
        pipeline.STATE["running"] = True
        try:
            dashboard = one.get("/?track=academic")
            self.assertEqual(dashboard.status_code, 200, dashboard.get_data(as_text=True))
            self.assertIn(b"Academic jobs", dashboard.data)
            self.assertIn(b"Industry jobs", dashboard.data)
        finally:
            pipeline.STATE["running"] = was_running

        query = "/api/opportunities?track=academic&min_score=0&limit=100&q=Example%20Engineering%20Group"
        first = one.get(query).get_json()
        second = two.get(query).get_json()
        item_one = next(x for x in first["items"] if x["id"] == OPP_IDS[0])
        item_two = next(x for x in second["items"] if x["id"] == OPP_IDS[0])
        self.assertGreater(item_one["score"], item_two["score"])

        missing_csrf = one.post("/api/status", json={"id": OPP_IDS[0], "status": "saved",
                                                       "track": "academic"})
        self.assertEqual(missing_csrf.status_code, 400)
        saved = one.post("/api/status", json={"id": OPP_IDS[0], "status": "saved",
                                              "track": "academic"},
                         headers={"X-CSRF-Token": csrf_one})
        self.assertEqual(saved.status_code, 200)
        other_view = two.get(f"/api/opportunity/{OPP_IDS[0]}?track=academic").get_json()
        self.assertEqual(other_view["status"], "new")

        config = one.post("/api/providers", json={
            "ai_provider": "openai", "ai_model": "gpt-test",
            "ai_base_url": "https://api.openai.com/v1/chat/completions",
            "ai_key": "plaintext-test-key-must-not-remain",
            "search_provider": "duckduckgo", "search_key": "",
        }, headers={"X-CSRF-Token": csrf_one})
        self.assertEqual(config.status_code, 200, config.get_data(as_text=True))
        conn = store.connect()
        try:
            stored = conn.execute("SELECT ai_key_enc FROM provider_configs WHERE user_id=?",
                                  (uid_one,)).fetchone()["ai_key_enc"]
            self.assertNotIn("plaintext-test-key", stored)
            conn.execute("""INSERT INTO application_packs
                (id,user_id,opportunity_id,profile_kind,status,zip_blob,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                ("__pack_test__", uid_one, OPP_IDS[0], "academic", "ready",
                 base64.b64encode(b"PK-test-private").decode(), "2026-09-21"))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(two.get("/api/packs/__pack_test__/download").status_code, 404)
        self.assertEqual(one.get("/api/packs/__pack_test__/download").status_code, 200)

        conn = store.connect()
        try:
            conn.execute("""INSERT INTO application_packs
                (id,user_id,opportunity_id,profile_kind,status,created_at)
                VALUES (?,?,?,?,?,?)""",
                ("__generated_pack__", uid_one, OPP_IDS[0], "academic", "working", "2026-09-21"))
            conn.commit()
        finally:
            conn.close()
        generated = json.dumps({
            "cover_letter": "## Application\n\n" + "Evidence-based tailored cover letter content. " * 12,
            "tailored_cv": "## Profile\n\n" + "Factual construction and infrastructure experience. " * 12,
        })
        sources = [{"title": "Department courses", "url": "https://example.invalid/courses",
                    "snippet": "Construction management course information.",
                    "query": "department courses", "retrieved_at": "2026-09-21"}]
        with patch.object(application_pack, "chat", return_value=generated), \
             patch.object(application_pack, "research_opportunity", return_value=sources):
            application_pack._generate("__generated_pack__", uid_one, OPP_IDS[0], "academic",
                                       ["cover_letter", "tailored_cv"])
        pack = application_pack.get_pack(uid_one, "__generated_pack__", include_blob=True)
        self.assertEqual(pack["status"], "ready", pack.get("error"))
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(pack["zip_blob"]))) as archive:
            names = set(archive.namelist())
            self.assertTrue({"Cover_Letter.docx", "Tailored_CV.docx", "Research Sources.docx",
                             "Job Advertisement.docx", "manifest.json"}.issubset(names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
