from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.hitb import HitbScraper


class HitbArchiveScraper(BaseCollectionScraper):
    assessor_id = "hitb"
    scraper_id = "hitb-presentations"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = HitbScraper(
            assessor_file=context.assessors_directory / "hitb.json",
            html_directory=context.html_directory / "hitb.zip",
            output_directory=context.output_directory / "hitb",
            profile_directory=context.profile_directory / "hitb",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout,
            retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results),
            endorsements=sum(item.endorsements for item in results),
            created=len(results),
            output_files=tuple(item.output for item in results),
        )
