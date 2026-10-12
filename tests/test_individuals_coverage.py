from __future__ import annotations

import json
import unittest
from pathlib import Path


class IndividualEndorsementCoverageTest(unittest.TestCase):
    """Every persisted individual must be backed by at least one endorsement."""

    def test_no_individual_has_zero_endorsements(self) -> None:
        individuals_directory = Path("data/individuals")
        zero_endorsements: list[str] = []

        for path in sorted(individuals_directory.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            endorsements = document.get("endorsements")
            stats_count = document.get("stats", {}).get("endorsements")
            if not endorsements or stats_count == 0:
                zero_endorsements.append(
                    f"{document.get('name', path.stem)} ({path.name})"
                )

        self.assertFalse(
            zero_endorsements,
            "Individuals with zero endorsements:\n" + "\n".join(zero_endorsements),
        )


if __name__ == "__main__":
    unittest.main()
