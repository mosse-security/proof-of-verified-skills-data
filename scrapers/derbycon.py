from __future__ import annotations

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.derbycon import DerbyConScraper


class DerbyConArchiveScraper(BaseCollectionScraper):
    assessor_id = "derbycon"
    scraper_id = "derbycon-archived-schedules"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = DerbyConScraper(
            assessor_file=context.assessors_directory / "derbycon.json",
            html_directory=context.html_directory / "derbycon.zip",
            output_directory=context.output_directory / "derbycon",
            profile_directory=context.profile_directory / "derbycon",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
