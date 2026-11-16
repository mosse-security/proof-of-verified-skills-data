from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.sans_holiday_hack import SansHolidayHackScraper


class SansHolidayHackWinnersScraper(BaseCollectionScraper):
    assessor_id = "sans-holiday-hack"
    scraper_id = "sans-holiday-hack-winners"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = SansHolidayHackScraper(
            assessor_file=context.assessors_directory / "sans-holiday-hack" / "sans-holiday-hack.json",
            archive_file=context.html_directory / "sans-holiday-hack.zip",
            output_directory=context.output_directory / "sans-holiday-hack",
            profile_directory=context.profile_directory / "sans-holiday-hack",
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
