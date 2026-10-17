import json
import tempfile
import unittest
from pathlib import Path

from scrapers.domains import ALLOWED_DOMAINS
from scrapers.identity_registry import IdentityRegistry
from scrapers.individuals import (
    _person_identity,
    build_assessor_individuals,
    merge_canonical_individuals,
    merge_endorsements,
)


class IdentityRegistryTests(unittest.TestCase):
    def test_person_identity_collapses_cosmetic_name_variants(self):
        self.assertEqual(
            _person_identity("Eloi San Felix"),
            _person_identity("Eloi Sanfelix"),
        )
        self.assertEqual(
            _person_identity("Eloi Sanfelix"),
            _person_identity("Eloi Sanfèlix"),
        )

    def test_whitelist_blacklist_and_unknown_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "individuals-enumeration.txt").write_text("Ada Lovelace\n", encoding="utf-8")
            (root / "individuals-blacklist.txt").write_text("Bad Person\n", encoding="utf-8")
            registry = IdentityRegistry(root)
            self.assertEqual(registry.decision("  ada   lovelace "), "allow")
            self.assertEqual(registry.decision("bad person"), "deny")
            self.assertEqual(registry.decision("New Person"), "unknown")
            self.assertEqual(registry.decision("new   person"), "unknown")
            self.assertEqual(
                (root / "individuals-not-validated.txt").read_text(encoding="utf-8").splitlines(),
                ["New Person"],
            )

    def test_blacklisted_names_are_not_recorded_as_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "individuals-blacklist.txt").write_text("Bad Person\n", encoding="utf-8")
            registry = IdentityRegistry(root)
            self.assertFalse(registry.allows("Bad Person"))
            self.assertEqual((root / "individuals-not-validated.txt").read_text(encoding="utf-8"), "")

    def test_reset_not_validated_starts_a_fresh_review_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = IdentityRegistry(root)
            self.assertEqual(registry.decision("Old Person"), "unknown")
            registry.reset_not_validated()
            self.assertEqual(
                (root / "individuals-not-validated.txt").read_text(encoding="utf-8"),
                "",
            )
            self.assertEqual(registry.decision("New Person"), "unknown")
            self.assertEqual(
                (root / "individuals-not-validated.txt").read_text(encoding="utf-8"),
                "New Person\n",
            )

    def test_unknown_stays_pending_until_manually_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = IdentityRegistry(root)
            self.assertEqual(registry.decision("Pending Person"), "unknown")
            self.assertFalse(registry.allows("Pending Person"))
            self.assertIn("Pending Person", (root / "individuals-not-validated.txt").read_text(encoding="utf-8"))

            (root / "individuals-enumeration.txt").write_text("Pending Person\n", encoding="utf-8")
            self.assertTrue(registry.allows("Pending Person"))

            (root / "individuals-enumeration.txt").write_text("", encoding="utf-8")
            (root / "individuals-blacklist.txt").write_text("Pending Person\n", encoding="utf-8")
            self.assertFalse(registry.allows("Pending Person"))

    def test_cached_lists_refresh_after_manual_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = IdentityRegistry(root)
            self.assertFalse(registry.allows("Edited Person"))

    def test_global_enumeration_rejects_normalized_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "individuals-enumeration.txt").write_text(
                "Ada Lovelace\nada   lovelace\n", encoding="utf-8"
            )
            registry = IdentityRegistry(root)
            with self.assertRaises(ValueError):
                registry.allows("Ada Lovelace")

    def test_global_enumeration_rejects_mojibake(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "individuals-enumeration.txt").write_text(
                "JÃ©rÃ©my Matos\n", encoding="utf-8"
            )
            registry = IdentityRegistry(root)
            with self.assertRaisesRegex(ValueError, "mojibake"):
                registry.allows("Jérémy Matos")

    def test_global_enumeration_is_utf8_and_unique(self):
        path = Path("data/individuals-enumeration.txt")
        text = path.read_bytes().decode("utf-8")
        self.assertNotIn("\ufffd", text)
        for marker in ("Ã", "Â", "â", "ƒ"):
            self.assertNotIn(marker, text)
        identities = [
            IdentityRegistry.normalize(line)
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(identities), len(set(identities)))

    def test_titles_are_removed_for_matching_and_pending_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "individuals-enumeration.txt").write_text(
                "Christian Folini\n", encoding="utf-8"
            )
            registry = IdentityRegistry(root)
            self.assertTrue(registry.allows("Dr. Christian Folini"))
            self.assertEqual(registry.normalize("Dr. Christian Folini"), "christian folini")

            (root / "individuals-enumeration.txt").write_text(
                "Edited Person\n", encoding="utf-8"
            )
            self.assertTrue(registry.allows("Edited Person"))

            (root / "individuals-enumeration.txt").write_text(
                "", encoding="utf-8"
            )
            (root / "individuals-blacklist.txt").write_text(
                "Edited Person\n", encoding="utf-8"
            )
            self.assertFalse(registry.allows("Edited Person"))

    def test_individual_merge_writes_only_whitelisted_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = IdentityRegistry(root)
            (root / "individuals-enumeration.txt").write_text("Allowed Person\n", encoding="utf-8")
            source = root / "endorsements"
            source.mkdir()
            record = {
                "name": "Allowed Person",
                "label": "A talk",
                "description": "A detailed description.",
                "type": "presentation",
                "assessor": "Example",
                "assessor-id": "example",
                "assessor-category": "conference_community",
                "assessor-rigor-level": "medium",
                "reviewType": "community_review",
                "subtitle": "Example 2026",
                "url": "https://example.test/talk",
                "evidence-links": [], "evidence": False,
                "povs": {"milestones": {"verifiable": False, "defended": False, "recognized": False, "trusted": False}, "level": 0, "explanation": "No evidence discovered for this record therefore it could not be verified"},
                "year": 2026, "domains": ["unknown"],
            }
            source.joinpath("records.json").write_text(json.dumps([record]), encoding="utf-8")
            result = merge_endorsements(source, root / "individuals", profiles_directory=root / "profiles", identity_registry=registry)
            self.assertEqual(result.people, 1)
            self.assertTrue((root / "individuals" / "allowed-person.json").exists())

    def test_merge_removes_profiles_after_whitelist_revocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = IdentityRegistry(root)
            (root / "individuals-enumeration.txt").write_text("Revoked Person\n", encoding="utf-8")
            source = root / "endorsements"
            source.mkdir()
            record = {
                "name": "Revoked Person", "label": "A talk", "description": "A detailed description.",
                "type": "presentation", "assessor": "Example", "assessor-id": "example",
                "assessor-category": "conference_community", "assessor-rigor-level": "medium",
                "reviewType": "community_review", "subtitle": "Example 2026",
                "url": "https://example.test/talk", "evidence-links": [], "evidence": False,
                "povs": {"milestones": {"verifiable": False, "defended": False, "recognized": False, "trusted": False}, "level": 0, "explanation": "No evidence discovered for this record therefore it could not be verified"},
                "year": 2026, "domains": ["unknown"],
            }
            source.joinpath("records.json").write_text(json.dumps([record]), encoding="utf-8")
            output = root / "individuals"
            merge_endorsements(source, output, profiles_directory=root / "profiles", identity_registry=registry)
            (root / "individuals-enumeration.txt").write_text("", encoding="utf-8")
            result = merge_endorsements(source, output, profiles_directory=root / "profiles", identity_registry=registry, allow_empty_output=True)
            self.assertEqual(result.people, 0)
            self.assertFalse((output / "revoked-person.json").exists())

    def test_merge_removes_zero_endorsement_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "individuals"
            output.mkdir()
            (output / "not-a-person.json").write_text(json.dumps({
                "name": "Not A Person", "last-updated": "2026-01-01T00:00:00Z",
                "biography": "", "contact": [],
                "stats": {"endorsements": 0}, "endorsements": [],
            }), encoding="utf-8")
            merge_endorsements(
                root / "endorsements", output,
                profiles_directory=root / "profiles", allow_empty_output=True,
            )
            self.assertFalse((output / "not-a-person.json").exists())

    def test_merge_clears_all_assessor_local_json_before_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessor_root = root / "assessors"
            stale = assessor_root / "example" / "individuals"
            stale.mkdir(parents=True)
            (stale / "old-record.json").write_text("{}", encoding="utf-8")
            nested = stale / "old-layout"
            nested.mkdir()
            (nested / "older-record.json").write_text("{}", encoding="utf-8")

            merge_endorsements(
                root / "endorsements",
                root / "individuals",
                profiles_directory=root / "profiles",
                assessors_directory=assessor_root,
                allow_empty_output=True,
            )

            self.assertEqual(list(stale.rglob("*.json")), [])
            self.assertEqual(list(stale.iterdir()), [])

    def test_scraper_stage_rebuilds_only_assessor_local_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessors = root / "assessors"
            assessor = assessors / "example"
            assessor.mkdir(parents=True)
            (root / "individuals-enumeration.txt").write_text(
                "Allowed Person\n", encoding="utf-8"
            )
            source = root / "staging" / "example"
            source.mkdir(parents=True)
            record = {
                "name": "Allowed Person", "label": "A talk",
                "description": "A detailed description.", "type": "presentation",
                "assessor": "Example", "assessor-id": "example",
                "assessor-category": "conference_community",
                "assessor-rigor-level": "medium", "reviewType": "community_review",
                "subtitle": "Example 2026", "url": "https://example.test/talk",
                "evidence-links": [], "evidence": False,
                "povs": {"milestones": {"verifiable": False, "defended": False,
                    "recognized": False, "trusted": False}, "level": 0,
                    "explanation": "No evidence discovered for this record therefore it could not be verified"},
                "year": 2026, "domains": ["unknown"],
            }
            source.joinpath("records.json").write_text(json.dumps([record]), encoding="utf-8")
            canonical = root / "individuals"
            canonical.mkdir()
            (canonical / "must-not-be-touched.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                build_assessor_individuals(
                    "example", endorsements_directory=root / "staging",
                    profiles_directory=root / "profiles", assessors_directory=assessors,
                ),
                1,
            )
            self.assertTrue((assessor / "individuals" / "allowed-person.json").exists())
            self.assertTrue((canonical / "must-not-be-touched.json").exists())

    def test_canonical_stage_deletes_stale_files_and_uses_local_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "assessors" / "example" / "individuals"
            local.mkdir(parents=True)
            document = {
                "name": "Allowed Person", "last-updated": "2026-01-01T00:00:00Z",
                "biography": "", "contact": [],
                "stats": {"endorsements": 0, "assessors": 0, "with-evidence": 0,
                    "without-evidence": 0, "by-domain": {domain: 0 for domain in ALLOWED_DOMAINS}},
                "endorsements": [],
            }
            local.joinpath("allowed-person.json").write_text(json.dumps(document), encoding="utf-8")
            output = root / "individuals"
            output.mkdir()
            (output / "stale.json").write_text("{}", encoding="utf-8")
            (output / "nested").mkdir()
            (output / "nested" / "stale.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                merge_canonical_individuals(assessors_directory=root / "assessors",
                                            output_directory=output),
                1,
            )
            self.assertFalse((output / "stale.json").exists())
            self.assertFalse((output / "nested").exists())
            self.assertTrue((output / "allowed-person.json").exists())


if __name__ == "__main__":
    unittest.main()
