from __future__ import annotations

import json
import unittest
from pathlib import Path

from scrapers.individuals import _looks_like_talk_title

INDIVIDUALS = Path("data/individuals")


class IndividualQualityUnitTests(unittest.TestCase):
    def test_known_short_schedule_titles_are_rejected(self):
        cases = (
            ("A girl", "Branden Miller and Emily Miller"),
            ("A SysCall to ARMs", "Brendan Watters"),
            ("Ansible", "Charles Yost"),
        )
        for name, label in cases:
            with self.subTest(name=name):
                self.assertTrue(_looks_like_talk_title(name, label))

    def test_known_reversed_profiles_are_not_active(self):
        for filename in ("a-girl.json", "a-syscall-to-arms.json", "ansible.json"):
            with self.subTest(filename=filename):
                self.assertFalse((INDIVIDUALS / filename).exists())

class IndividualQualityTest(unittest.TestCase):
    """Generated individual names must not be obvious talk-title records."""

    def test_profiles_have_person_like_names(self) -> None:
        failures: list[str] = []
        for path in sorted(Path("data/individuals").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            name = str(document.get("name", ""))
            if any(
                _looks_like_talk_title(name, str(record.get("label", "")))
                for record in document.get("endorsements", [])
                if isinstance(record, dict)
            ):
                failures.append(f"{name} ({path.name})")
        self.assertFalse(failures, "Title-shaped individual names:\n" + "\n".join(failures))
