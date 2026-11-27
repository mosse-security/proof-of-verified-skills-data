from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from scrapers import (
    ENDORSEMENT_FIELDS,
    EndorsementSchemaError,
    AssessorMetadata,
    build_endorsement_record,
    is_non_endorsement_session,
    validate_endorsement_record,
)


class EndorsementSchemaTests(unittest.TestCase):
    def test_assessor_countries_validate_and_preserve_order(self) -> None:
        document = {"id": "example", "name": "Example", "category": "conference_community", "peerReview": {"rigorLevel": "medium", "reviewType": "community_review"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.json"
            for countries in ([], ["Worldwide"], ["United States", "Canada"]):
                document["countries"] = countries
                path.write_text(json.dumps(document), encoding="utf-8")
                self.assertEqual(AssessorMetadata.from_file(path).countries, tuple(countries))
            for countries in ("Worldwide", ["Worldwide", "Canada"], ["Canada", "Canada"], [""], [42]):
                document["countries"] = countries
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(EndorsementSchemaError):
                    AssessorMetadata.from_file(path)

    def test_existing_assessor_countries_are_valid(self) -> None:
        files = [path / f"{path.name}.json" for path in Path("data/assessors").iterdir() if path.is_dir() and (path / f"{path.name}.json").is_file()]
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=path):
                self.assertIn("countries", json.loads(path.read_text(encoding="utf-8")))
                AssessorMetadata.from_file(path)

    def test_library_contract_matches_endorsement_template(self) -> None:
        template = json.loads(
            re.sub(r",\s*\.\.\.", "", Path("data/templates/endorsement.tpl").read_text(encoding="utf-8"))
        )

        self.assertEqual(set(ENDORSEMENT_FIELDS), set(template))

    def test_builder_emits_only_template_fields_and_validator_rejects_extras(self) -> None:
        assessor = AssessorMetadata(
            id="example",
            name="Example Conference",
            category="conference_community",
            rigor_level="medium",
            review_type="community_review",
        )
        record = build_endorsement_record(
            name="Alice Example",
            label="Breaking Things Safely",
            description="A detailed description of the talk.",
            endorsement_type="presentation",
            assessor=assessor,
            subtitle="Example Conference 2026",
            location="Canada",
            url="https://example.test/talk",
            year=2026,
            domains=("vulnerability-research",),
            evidence_links=({"title": "Example Conference - Talk", "url": "https://www.youtube.com/watch?v=abc123"},),
        )

        self.assertEqual(set(record), set(ENDORSEMENT_FIELDS))
        record["legacyField"] = "not in the template"
        with self.assertRaises(EndorsementSchemaError):
            validate_endorsement_record(record, assessor=assessor)

    def test_description_must_be_non_empty(self) -> None:
        assessor = AssessorMetadata(
            id="example",
            name="Example Conference",
            category="conference_community",
            rigor_level="medium",
            review_type="community_review",
        )
        with self.assertRaises(EndorsementSchemaError):
            build_endorsement_record(
                name="Alice Example",
                label="Untitled Talk",
                description=" ",
                endorsement_type="presentation",
                assessor=assessor,
                url="https://example.test/talk",
                year=2026,
                domains=("unknown",),
            )

    def test_povs_follow_evidence_state(self) -> None:
        assessor = AssessorMetadata(
            id="example", name="Example Conference", category="conference_community",
            rigor_level="medium", review_type="community_review",
        )
        with_evidence = build_endorsement_record(
            name="Alice Example", label="Talk", description="Detailed talk abstract.",
            endorsement_type="presentation", assessor=assessor, url="https://example.test/talk",
            year=2026, domains=("vulnerability-research",),
            evidence_links=({"title": "Example Conference - Talk", "url": "https://www.youtube.com/watch?v=abc123"},),
        )
        self.assertEqual(with_evidence["povs-taxonomy"]["evidence"], "observable")
        self.assertIs(with_evidence["povs-taxonomy"]["verifiable"], True)
        without_evidence = build_endorsement_record(
            name="Alice Example", label="Talk", description="Detailed talk abstract.",
            endorsement_type="presentation", assessor=assessor, url="https://example.test/talk",
            year=2026, domains=("vulnerability-research",),
        )
        self.assertEqual(without_evidence["povs-taxonomy"]["evidence"], "indirect")

    def test_judged_result_is_independently_reviewed(self) -> None:
        assessor = AssessorMetadata(
            id="pwn2own", name="Pwn2Own", category="competition",
            rigor_level="very_high", review_type="competition_validation",
        )
        record = build_endorsement_record(
            name="Alice Example", label="Pwn2Own result", description="Validated exploit.",
            endorsement_type="competition_result", assessor=assessor,
            url="https://example.test/result", year=2026, domains=("vulnerability-research",),
        )
        self.assertEqual(record["povs-taxonomy"]["evidence"], "independently-reviewed")
        self.assertTrue(record["povs-taxonomy"]["competition"])
        validate_endorsement_record(record, assessor=assessor)

    def test_academic_paper_and_linked_video(self) -> None:
        assessor = AssessorMetadata("ieee-sp", "IEEE S&P", "conference_academic",
                                    "very_high", "double_blind")
        fields = dict(name="Alice Example", label="Systems Research", description="Research paper.",
                      endorsement_type="presentation", url="https://example.test/program",
                      year=2026, domains=("unknown",))
        paper = build_endorsement_record(assessor=assessor, **fields)
        self.assertEqual(paper["type"], "paper")
        self.assertEqual(paper["povs-taxonomy"]["evidence"], "independently-reviewed")
        self.assertIs(paper["povs-taxonomy"]["verifiable"], True)

        conference = AssessorMetadata("example", "Example", "conference_community",
                                      "medium", "community_review")
        talk = build_endorsement_record(assessor=conference, **fields,
            evidence_links=[{"title": "Conference recording", "url": "https://youtu.be/other"}])
        self.assertEqual(talk["povs-taxonomy"]["evidence"], "observable")

    def test_work_link_floor_applies_across_types_and_preserves_review(self) -> None:
        from scrapers.taxonomy import apply_evidence_floor

        for title, url in [
            ("Source", "https://github.com/example/tool"),
            ("Read", "https://example.test/paper.pdf"),
            ("Paper", "https://example.test/article"),
            ("Session replay", "https://www.youtube.com/watch?v=123"),
        ]:
            for initial, expected in [("indirect", "observable"), ("independently-reviewed", "independently-reviewed")]:
                with self.subTest(url=url, initial=initial):
                    taxonomy = {"evidence": initial, "verifiable": "unknown", "trusted": True}
                    record = {"type": "tool", "url": "https://example.test/awards",
                              "evidence-links": [{"title": title, "url": url}], "povs-taxonomy": taxonomy}
                    apply_evidence_floor(record)
                    self.assertEqual(taxonomy["evidence"], expected)
                    self.assertIs(taxonomy["verifiable"], True)
                    self.assertIs(taxonomy["trusted"], True)

    def test_recognition_link_alone_is_indirect(self) -> None:
        from scrapers.taxonomy import links_to_work

        self.assertFalse(links_to_work({"title": "Leaderboard", "url": "https://example.test/winners"}))

    def test_bug_bounty_requires_award_credit_on_rankings(self) -> None:
        for kind, issuer, description, awarded in [
            ("bug_bounty", "mozilla-security", "Bounty Hall of Fame credit.", True),
            ("recognition", "google-security-rewards", "Public profile records 3 awards.", True),
            ("recognition", "google-security-rewards", "Public profile records 0 awards.", False),
            ("recognition", "another-programme", "Public profile records 3 awards.", False),
        ]:
            with self.subTest(issuer=issuer, description=description):
                record = build_endorsement_record(
                    name="Alice Example", label="Programme credit", description=description,
                    endorsement_type=kind, assessor=AssessorMetadata(issuer, issuer, "vendor", "high", "internal_review"),
                    url="https://example.test/credit", year=2026, domains=("unknown",),
                )
                taxonomy = record["povs-taxonomy"]
                self.assertEqual(taxonomy["evidence"], "independently-reviewed" if awarded else "indirect")
                for key in ("trusted", "production"):
                    self.assertEqual(taxonomy[key], True if awarded else "unknown")
                self.assertEqual(taxonomy["verifiable"], "unknown")

    def test_cve_endorsements_are_only_vulnerability_research(self) -> None:
        assessor = AssessorMetadata(
            id="mitre", name="MITRE CVE Program", category="vulnerability_database",
            rigor_level="high", review_type="committee_review",
        )
        record = build_endorsement_record(
            name="Alice Example", label="CVE-2026-1234", description="A published vulnerability.",
            endorsement_type="vulnerability_discovery", assessor=assessor,
            url="https://www.cve.org/CVERecord?id=CVE-2026-1234", year=2026,
            domains=("vulnerability-research",),
            evidence_links=({"title": "CVE record", "url": "https://www.cve.org/CVERecord?id=CVE-2026-1234"},),
        )
        record["domains"] = ["cloud-security", "vulnerability-research"]
        record["subspecialties"] = {
            "cloud-security": [],
            "vulnerability-research": ["cve-analysis-and-vulnerability-disclosure"],
        }
        with self.assertRaises(EndorsementSchemaError):
            validate_endorsement_record(record, assessor=assessor)

    def test_povs_cannot_disagree_with_evidence(self) -> None:
        assessor = AssessorMetadata(
            id="example", name="Example Conference", category="conference_community",
            rigor_level="medium", review_type="community_review",
        )
        record = build_endorsement_record(
            name="Alice Example", label="Talk", description="Detailed talk abstract.",
            endorsement_type="presentation", assessor=assessor, url="https://example.test/talk",
            year=2026, domains=("vulnerability-research",),
        )
        record["povs-taxonomy"]["evidence"] = "observable"
        with self.assertRaises(EndorsementSchemaError):
            validate_endorsement_record(record, assessor=assessor)

    def test_non_endorsement_filter_requires_classifiable_event_text(self) -> None:
        self.assertTrue(
            is_non_endorsement_session(
                "DEF CON 101",
                "A long orientation panel covering the conference community and program "
                "for new attendees. " * 2,
            )
        )
        self.assertFalse(is_non_endorsement_session("Panel: Meet the Feds", "No abstract provided."))


if __name__ == "__main__":
    unittest.main()


