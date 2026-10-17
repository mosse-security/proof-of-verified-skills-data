from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.ccc import CccScraper


class CccArchiveScraper(BaseCollectionScraper):
    assessor_id = "ccc"
    scraper_id = "ccc-recordings"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = CccScraper(
            assessor_file=context.assessors_directory / "ccc" / "ccc.json",
            html_directory=context.html_directory / "ccc.zip",
            output_directory=context.output_directory / "ccc",
            profile_directory=context.profile_directory / "ccc",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
