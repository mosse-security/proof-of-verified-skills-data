from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.pwn2own import Pwn2OwnScraper


class Pwn2OwnArchiveScraper(BaseCollectionScraper):
    assessor_id = "pwn2own"
    scraper_id = "pwn2own-results"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = Pwn2OwnScraper(
            assessor_file=context.assessors_directory / "pwn2own" / "pwn2own.json",
            html_directory=context.html_directory / "pwn2own.zip",
            output_directory=context.output_directory / "pwn2own",
            profile_directory=context.profile_directory / "pwn2own",
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
