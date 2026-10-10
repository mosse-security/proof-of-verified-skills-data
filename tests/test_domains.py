from __future__ import annotations

import unittest

from endorsement_scraper import Endorsement, OrganizationMetadata, detect_domains, normalize_domains
from endorsement_scraper.domains import DomainMappingError, validate_record_domains


class DomainMappingTests(unittest.TestCase):
    def test_detects_multiple_domains_in_taxonomy_order(self) -> None:
        domains = detect_domains(
            "AWS incident response with digital forensics, red teaming, and fuzzing"
        )

        self.assertEqual(
            domains,
            (
                "cloud security",
                "digital forensics",
                "incident response",
                "red teaming",
                "vulnerability research",
            ),
        )

    def test_unknown_is_used_when_no_rule_matches(self) -> None:
        self.assertEqual(detect_domains("A talk about security culture"), ("unknown",))

    def test_vulnerability_language_maps_without_a_numeric_cve(self) -> None:
        self.assertEqual(
            detect_domains(
                "A multi-stage exploit chain with authentication bypass, "
                "sandbox escape, full RCE, and proof-of-concept release"
            ),
            ("vulnerability research",),
        )

    def test_supply_chain_backdoor_maps_to_devsecops_and_vulnerability_research(self) -> None:
        self.assertEqual(
            detect_domains(
                "An open-source project was compromised through an upstream "
                "library backdoor"
            ),
            ("devsecops", "vulnerability research"),
        )

    def test_endorsement_always_has_mapped_domains(self) -> None:
        endorsement = Endorsement(
            organization_id="example",
            kind="conference_presentation",
            title="Kubernetes penetration testing and incident response",
            recipient="Alice Example",
            source_url="https://example.test/talk",
            year=2026,
        )
        record = endorsement.to_record(
            organization=OrganizationMetadata(
                id="example",
                name="Example",
                category="conference_community",
                review_type="community_review",
            )
        )

        self.assertEqual(
            record["domains"],
            ["cloud security", "incident response", "penetration testing"],
        )
        validate_record_domains(record)

    def test_explicit_domains_are_normalized_and_invalid_values_fail(self) -> None:
        self.assertEqual(
            normalize_domains(["GRC", "cloud security", "GRC"]),
            ("cloud security", "GRC"),
        )
        with self.assertRaises(DomainMappingError):
            normalize_domains(["application security"])


if __name__ == "__main__":
    unittest.main()
