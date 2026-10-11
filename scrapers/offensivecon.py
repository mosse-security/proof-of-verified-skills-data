from __future__ import annotations

import os
from pathlib import Path

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.offensivecon import OffensiveConScraper


class OffensiveConArchiveScraper(BaseCollectionScraper):
    assessor_id = "offensivecon"
    scraper_id = "offensivecon-talks"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = OffensiveConScraper(
            assessor_file=context.assessors_directory / "offensivecon.json",
            html_directory=context.html_directory / "offensivecon.zip",
            output_directory=context.output_directory / "offensivecon",
            profile_directory=context.profile_directory / "offensivecon",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout,
            retries=context.retries,
        ).run()
        return CollectionScraperResult(pages=len(results), endorsements=sum(item.endorsements for item in results), created=len(results), output_files=tuple(item.output for item in results))
