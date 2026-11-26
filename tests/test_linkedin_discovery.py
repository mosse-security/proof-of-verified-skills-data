from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "discover_linkedin_profiles.py"
SPEC = importlib.util.spec_from_file_location("linkedin_discovery", SCRIPT)
assert SPEC and SPEC.loader
linkedin_discovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(linkedin_discovery)


class LinkedInDiscoveryTests(unittest.TestCase):
    def test_normalizes_public_profile_urls(self) -> None:
        self.assertEqual(
            linkedin_discovery.canonical_linkedin_url("https://linkedin.com/in/Alice-Example/?trk=public"),
            "https://www.linkedin.com/in/Alice-Example",
        )

    def test_rejects_non_profile_linkedin_urls(self) -> None:
        self.assertIsNone(linkedin_discovery.canonical_linkedin_url("https://www.linkedin.com/company/example"))
        self.assertIsNone(linkedin_discovery.canonical_linkedin_url("https://example.com/in/alice"))

    def test_candidates_keep_only_personal_profile_urls(self) -> None:
        candidates = linkedin_discovery.candidates_for(
            [
                {"url": "https://www.linkedin.com/company/example", "title": "Example", "snippet": ""},
                {"url": "https://www.linkedin.com/in/alice-example/?trk=x", "title": "Alice Example", "snippet": ""},
            ],
            "Alice Example",
        )
        self.assertEqual(candidates[0]["url"], "https://www.linkedin.com/in/alice-example")
        self.assertEqual(len(candidates), 1)

    def test_candidates_identify_explicit_cybersecurity_context(self) -> None:
        candidates = linkedin_discovery.candidates_for(
            [{
                "url": "https://www.linkedin.com/in/alice-example",
                "title": "Alice Example - Information Security Researcher",
                "snippet": "Cybersecurity professional",
            }],
            "Alice Example",
        )
        self.assertTrue(candidates[0]["cybersecurity_context"])

    def test_query_uses_the_simple_requested_linkedin_cyber_search(self) -> None:
        self.assertEqual(
            linkedin_discovery.linkedin_query_for({"name": "Alice Example"}),
            'site:linkedin.com "Alice Example" AND "Cyber"',
        )

    def test_apply_ignores_an_approved_url_not_in_the_review_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "review.json"
            review.write_text(json.dumps({"people": [{
                "slug": "alice-example",
                "name": "Alice Example",
                "candidates": [{"url": "https://www.linkedin.com/in/alice-example"}],
                "review": {"approved": True, "selected_url": "https://www.linkedin.com/in/someone-else"},
            }]}), encoding="utf-8")
            old_contacts = linkedin_discovery.CONTACTS
            try:
                linkedin_discovery.CONTACTS = root / "contacts"
                linkedin_discovery.apply_approved(review)
                self.assertFalse((linkedin_discovery.CONTACTS / "alice-example.json").exists())
            finally:
                linkedin_discovery.CONTACTS = old_contacts

    def test_high_confidence_accepts_one_full_name_cybersecurity_match(self) -> None:
        candidate = {
            "url": "https://www.linkedin.com/in/alice-example",
            "name_terms_matched": 2,
            "cybersecurity_context": True,
        }
        url, reason = linkedin_discovery.high_confidence_url(
            "Alice Example",
            [candidate],
        )
        self.assertEqual(url, "https://www.linkedin.com/in/alice-example")
        self.assertIn("sole full-name LinkedIn profile", reason)

    def test_high_confidence_rejects_a_match_without_cybersecurity_context(self) -> None:
        url, _ = linkedin_discovery.high_confidence_url(
            "Alice Example",
            [{"url": "https://www.linkedin.com/in/alice-example", "name_terms_matched": 2, "cybersecurity_context": False}],
        )
        self.assertIsNone(url)

    def test_high_confidence_rejects_multiple_namesakes(self) -> None:
        url, reason = linkedin_discovery.high_confidence_url(
            "Alice Example",
            [
                {"url": "https://www.linkedin.com/in/alice-example", "name_terms_matched": 2, "cybersecurity_context": True},
                {"url": "https://www.linkedin.com/in/another-alice-example", "name_terms_matched": 2, "cybersecurity_context": True},
            ],
        )
        self.assertIsNone(url)
        self.assertIn("name is not unique", reason)

    def test_high_confidence_rejects_non_cybersecurity_namesakes_too(self) -> None:
        url, reason = linkedin_discovery.high_confidence_url(
            "Alice Example",
            [
                {"url": "https://www.linkedin.com/in/alice-example", "name_terms_matched": 2, "cybersecurity_context": True},
                {"url": "https://www.linkedin.com/in/another-alice-example", "name_terms_matched": 2, "cybersecurity_context": False},
            ],
        )
        self.assertIsNone(url)
        self.assertIn("name is not unique", reason)

    def test_write_linkedin_contact_updates_the_contact_information_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_contacts = linkedin_discovery.CONTACTS
            try:
                linkedin_discovery.CONTACTS = root / "data" / "contact-information"
                linkedin_discovery.CONTACTS.mkdir(parents=True)
                destination = linkedin_discovery.CONTACTS / "alice-example.json"
                destination.write_text(
                    json.dumps({"name": "Alice Example", "contact": [{"label": "github", "url": "https://github.com/alice"}]}),
                    encoding="utf-8",
                )
                self.assertTrue(linkedin_discovery.write_linkedin_contact(
                    "alice-example", "Alice Example", "https://www.linkedin.com/in/alice-example"
                ))
                updated = json.loads(destination.read_text(encoding="utf-8"))
                self.assertEqual(updated["contact"], [
                    {"label": "github", "url": "https://github.com/alice"},
                    {
                        "label": "linkedin",
                        "url": "https://www.linkedin.com/in/alice-example",
                        "source": "povs-linkedin-discovery",
                    },
                ])
            finally:
                linkedin_discovery.CONTACTS = old_contacts


if __name__ == "__main__":
    unittest.main()
