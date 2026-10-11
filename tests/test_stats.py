from __future__ import annotations

import unittest
from datetime import datetime, timezone

from endorsement_scraper.runner import RunReport, ScraperReport
from endorsement_scraper.stats import build_run_stats, validate_run_stats


class RunStatsTests(unittest.TestCase):
    def test_stats_capture_counts_and_pass_defcon_sanity_check(self) -> None:
        report = RunReport([ScraperReport("def-con-speakers", "def-con", pages=34, endorsements=4145)])
        stats = build_run_stats(report, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc), finished_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
        validate_run_stats(stats)
        self.assertEqual(stats["totals"]["endorsements"], 4145)
        self.assertEqual(stats["status"], "ok")

    def test_zero_defcon_endorsements_are_marked_failed(self) -> None:
        report = RunReport([ScraperReport("def-con-speakers", "def-con", pages=34, endorsements=0)])
        stats = build_run_stats(report, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(stats["status"], "failed")
        validate_run_stats(stats)
        self.assertFalse(stats["validations"][0]["passed"])
