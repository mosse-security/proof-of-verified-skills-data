from __future__ import annotations

import json
import unittest
from pathlib import Path

from endorsement_scraper import (
    ENDORSEMENT_FIELDS,
    EndorsementSchemaError,
    OrganizationMetadata,
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
        organization = OrganizationMetadata(
            id="example",
            name="Example Conference",
            category="conference_community",
            review_type="community_review",
        )
        record = build_endorsement_record(
            name="Alice Example",
            label="Breaking Things Safely",
            endorsement_type="presentation",
            organization=organization,
            subtitle="Example Conference 2026",
            url="https://example.test/talk",
            year=2026,
            domains=("vulnerability research",),
        )

        self.assertEqual(set(record), set(ENDORSEMENT_FIELDS))
        record["legacyField"] = "not in the template"
        with self.assertRaises(EndorsementSchemaError):
            validate_endorsement_record(record, organization=organization)


if __name__ == "__main__":
    unittest.main()
