from __future__ import annotations

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.grrcon import GrrconScraper


class GrrconArchiveScraper(BaseCollectionScraper):
    assessor_id = "grrcon"
    scraper_id = "grrcon-presentations"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = GrrconScraper(
            assessor_file=context.assessors_directory / "grrcon.json",
            html_directory=context.html_directory / "grrcon.zip",
            output_directory=context.output_directory / "grrcon",
            profile_directory=context.profile_directory / "grrcon",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
