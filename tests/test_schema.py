from __future__ import annotations

import json
import unittest
from pathlib import Path

from endorsement_scraper import (
    ENDORSEMENT_FIELDS,
    EndorsementSchemaError,
    AssessorMetadata,
    build_endorsement_record,
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
            domains=("vulnerability research",),
            additional_links=({"title": "Recording", "url": "https://example.test/video"},),
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


if __name__ == "__main__":
    unittest.main()


