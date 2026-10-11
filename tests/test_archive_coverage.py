from __future__ import annotations

import unittest

from endorsement_scraper.archive_coverage import missing_archive_urls


class ArchiveCoverageTest(unittest.TestCase):
    def test_every_configured_process_url_is_archived(self) -> None:
        missing = missing_archive_urls()
        if not missing:
            return
        details = [
            f"{assessor}:\n" + "\n".join(f"  - {url}" for url in urls)
            for assessor, urls in missing.items()
        ]
        self.fail(
            "Configured process URLs are missing from local archives. "
            "Download them manually and place them in the assessor ZIP, then rerun:\n"
            + "\n".join(details)
        )
