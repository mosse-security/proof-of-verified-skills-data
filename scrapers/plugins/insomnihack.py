from __future__ import annotations

from pathlib import Path

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.insomnihack import InsomnihackScraper


class InsomnihackArchiveScraper(BaseCollectionScraper):
    assessor_id = "insomnihack"
    scraper_id = "insomnihack-talks"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = InsomnihackScraper(
            assessor_file=context.assessors_directory / "insomnihack" / "insomnihack.json",
            html_directory=context.html_directory / "insomnihack.zip",
            output_directory=context.output_directory / "insomnihack",
            profile_directory=context.profile_directory / "insomnihack",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout,
            retries=context.retries,
        ).run()
        return CollectionScraperResult(pages=len(results), endorsements=sum(item.endorsements for item in results), created=len(results), output_files=tuple(item.output for item in results))
