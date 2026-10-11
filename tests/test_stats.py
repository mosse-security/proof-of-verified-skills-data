from __future__ import annotations

import unittest
from datetime import datetime, timezone

from endorsement_scraper.runner import RunReport, ScraperReport
from endorsement_scraper.stats import build_run_stats, validate_run_stats


class RunStatsTests(unittest.TestCase):
    def test_stats_capture_counts_and_pass_defcon_sanity_check(self) -> None:
        report = RunReport([ScraperReport("def-con-speakers", "def-con", pages=34, endorsements=4145)])
        stats = build_run_stats(report, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc), finished_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc), evidence_counts=(4000, 145))
        validate_run_stats(stats)
        self.assertEqual(stats["totals"]["endorsements"], 4145)
        self.assertEqual(stats["status"], "ok")
        self.assertEqual(stats["evidence"]["with-links"], 4000)
        self.assertEqual(stats["totals"]["by-domain"]["unknown"], 0)
        self.assertEqual(stats["totals"]["individuals"], 0)

    def test_zero_defcon_endorsements_are_marked_failed(self) -> None:
        report = RunReport([ScraperReport("def-con-speakers", "def-con", pages=34, endorsements=0)])
        stats = build_run_stats(report, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc), evidence_counts=(0, 0))
        self.assertEqual(stats["status"], "failed")
        validate_run_stats(stats)
        self.assertFalse(stats["validations"][0]["passed"])
