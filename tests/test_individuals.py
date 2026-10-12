from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from endorsement_scraper.individuals import (
    IndividualMergeError,
    cleanup_generated_directory,
    merge_endorsements,
)


def endorsement(name: str, label: str, year: int = 2026) -> dict[str, object]:
    return {
        "name": name,
        "label": label,
        "description": f"Detailed description for {label}.",
        "type": "presentation",
        "assessor": "Example Conference",
        "assessor-id": "example",
        "assessor-category": "conference_community",
        "assessor-rigor-level": "medium",
        "reviewType": "community_review",
        "subtitle": "Example 2026",
        "url": f"https://example.test/{label.replace(' ', '-')}",
        "evidence-links": [],
        "evidence": False,
        "year": year,
        "domains": ["unknown"],
    }


class IndividualMergeTests(unittest.TestCase):
    def test_cleanup_removes_temporary_children_but_keeps_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "tmp"
            (root / "endorsements" / "def-con").mkdir(parents=True)
            (root / "profiles" / "def-con").mkdir(parents=True)
            (root / "endorsements" / "def-con" / "one.json").write_text("{}")
            (root / "profiles" / "def-con" / "one.json").write_text("{}")

            removed = cleanup_generated_directory(root)

            self.assertEqual(removed, 2)
            self.assertTrue(root.is_dir())
            self.assertEqual(list(root.iterdir()), [])

    def test_groups_case_insensitive_names_and_deduplicates_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "endorsements" / "example"
            source.mkdir(parents=True)
            records = [
                endorsement("Alice Example", "Second Talk"),
                endorsement("alice   example", "First Talk", 2025),
                endorsement("Alice Example", "Second Talk"),
            ]
            (source / "records.json").write_text(json.dumps(records), encoding="utf-8")

            result = merge_endorsements(
                root / "endorsements", root / "individuals", profiles_directory=root / "profiles"
            )

            self.assertEqual(result.people, 1)
            self.assertEqual(result.endorsements, 2)
            document = json.loads(
                (root / "individuals" / "alice-example.json").read_text()
            )
            self.assertEqual(document["name"], "Alice Example")
            self.assertEqual([item["year"] for item in document["endorsements"]], [2025, 2026])
            self.assertEqual(document["biography"], "")
            self.assertEqual(document["contact"], [])
            self.assertEqual(document["stats"]["endorsements"], 2)
            self.assertEqual(document["stats"]["assessors"], 1)
            self.assertEqual(document["stats"]["without-evidence"], 2)
            self.assertEqual(document["stats"]["by-domain"]["unknown"], 2)

    def test_merges_records_from_unlimited_assessor_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for assessor_id, assessor_name in (("one", "Assessor One"), ("two", "Assessor Two")):
                source = root / "endorsements" / assessor_id
                source.mkdir(parents=True)
                record = endorsement("Shared Person", f"{assessor_name} Talk")
                record["assessor"] = assessor_name
                record["assessor-id"] = assessor_id
                (source / "records.json").write_text(json.dumps([record]), encoding="utf-8")

            result = merge_endorsements(
                root / "endorsements", root / "individuals", profiles_directory=root / "profiles"
            )

            self.assertEqual(result.people, 1)
            self.assertEqual(result.endorsements, 2)
            document = json.loads((root / "individuals" / "shared-person.json").read_text())
            self.assertEqual({item["assessor-id"] for item in document["endorsements"]}, {"one", "two"})
            self.assertEqual(document["stats"]["assessors"], 2)

    def test_rerun_overwrites_without_appending_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "endorsements"
            source.mkdir()
            (source / "one.json").write_text(
                json.dumps([endorsement("Bob Example", "Talk")]), encoding="utf-8"
            )
            first = merge_endorsements(
                source, root / "individuals", profiles_directory=root / "profiles"
            )
            second = merge_endorsements(
                source, root / "individuals", profiles_directory=root / "profiles"
            )
            self.assertEqual(first.created, 1)
            self.assertEqual(second.overwritten, 0)
            self.assertEqual(second.skipped, 1)
            self.assertEqual(second.endorsements, 1)

    def test_last_updated_is_preserved_when_content_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "endorsements"
            source.mkdir()
            (source / "one.json").write_text(
                json.dumps([endorsement("Casey Example", "Talk")]), encoding="utf-8"
            )
            output = root / "individuals"
            with patch("endorsement_scraper.individuals._utc_timestamp", return_value="2026-01-01T00:00:00Z"):
                merge_endorsements(source, output, profiles_directory=root / "profiles")
            path = output / "casey-example.json"
            first = json.loads(path.read_text())

            with patch("endorsement_scraper.individuals._utc_timestamp", return_value="2026-01-02T00:00:00Z"):
                merge_endorsements(source, output, profiles_directory=root / "profiles")
            second = json.loads(path.read_text())

            self.assertEqual(first["last-updated"], "2026-01-01T00:00:00Z")
            self.assertEqual(second["last-updated"], first["last-updated"])

    def test_last_updated_changes_when_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "endorsements"
            source.mkdir()
            source_file = source / "one.json"
            source_file.write_text(
                json.dumps([endorsement("Dana Example", "Talk")]), encoding="utf-8"
            )
            output = root / "individuals"
            with patch("endorsement_scraper.individuals._utc_timestamp", return_value="2026-01-01T00:00:00Z"):
                merge_endorsements(source, output, profiles_directory=root / "profiles")
            source_file.write_text(
                json.dumps([endorsement("Dana Example", "Updated Talk")]), encoding="utf-8"
            )
            with patch("endorsement_scraper.individuals._utc_timestamp", return_value="2026-01-02T00:00:00Z"):
                merge_endorsements(source, output, profiles_directory=root / "profiles")
            document = json.loads((output / "dana-example.json").read_text())
            self.assertEqual(document["last-updated"], "2026-01-02T00:00:00Z")

    def test_refuses_empty_existing_output_to_protect_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "endorsements"
            source.mkdir(parents=True)
            (source / "one.json").write_text(
                json.dumps([endorsement("Empty Output", "Talk")]), encoding="utf-8"
            )
            output = root / "individuals"
            output.mkdir()
            with self.assertRaises(IndividualMergeError):
                merge_endorsements(source, output, profiles_directory=root / "profiles")


if __name__ == "__main__":
    unittest.main()


