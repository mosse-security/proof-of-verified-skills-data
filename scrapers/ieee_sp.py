from __future__ import annotations

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.ieee_sp import IeeeSpScraper


class IeeeSpArchiveScraper(BaseCollectionScraper):
    assessor_id = "ieee-sp"
    scraper_id = "ieee-sp-accepted-papers"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = IeeeSpScraper(
            assessor_file=context.assessors_directory / "ieee-sp.json",
            html_directory=context.html_directory / "ieee-sp.zip",
            output_directory=context.output_directory / "ieee-sp",
            profile_directory=context.profile_directory / "ieee-sp",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
