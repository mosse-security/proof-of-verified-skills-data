from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.ndss import NdssScraper


class NdssArchiveScraper(BaseCollectionScraper):
    assessor_id = "ndss"
    scraper_id = "ndss-accepted-papers"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = NdssScraper(
            assessor_file=context.assessors_directory / "ndss.json",
            html_directory=context.html_directory / "ndss.zip",
            output_directory=context.output_directory / "ndss",
            profile_directory=context.profile_directory / "ndss",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
