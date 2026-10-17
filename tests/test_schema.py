from __future__ import annotations

import json
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
    def test_library_contract_matches_endorsement_template(self) -> None:
        template = json.loads(
            Path("data/templates/endorsement.tpl").read_text(encoding="utf-8")
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
            url="https://example.test/talk",
            year=2026,
            domains=("vulnerability-research",),
            evidence_links=({"title": "Recording", "url": "https://example.test/video"},),
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
            evidence_links=({"title": "Recording", "url": "https://example.test/video"},),
        )
        self.assertEqual(with_evidence["povs"]["level"], 2)
        self.assertTrue(with_evidence["povs"]["milestones"]["verifiable"])
        self.assertIn("real consequence", with_evidence["povs"]["explanation"])
        without_evidence = build_endorsement_record(
            name="Alice Example", label="Talk", description="Detailed talk abstract.",
            endorsement_type="presentation", assessor=assessor, url="https://example.test/talk",
            year=2026, domains=("vulnerability-research",),
        )
        self.assertEqual(without_evidence["povs"]["level"], 0)
        self.assertEqual(
            without_evidence["povs"]["explanation"],
            "No evidence discovered for this record therefore it could not be verified",
        )

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
        record["povs"]["level"] = 2
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


