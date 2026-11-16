from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.mozilla_security import MozillaSecurityScraper


class MozillaWebHallOfFameScraper(BaseCollectionScraper):
    assessor_id = "mozilla-security"
    scraper_id = "mozilla-web-hall-of-fame"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = MozillaSecurityScraper(
            assessor_file=context.assessors_directory / "mozilla-security" / "mozilla-security.json",
            html_directory=context.html_directory / "mozilla-security.zip",
            output_directory=context.output_directory / "mozilla-security",
            profile_directory=context.profile_directory / "mozilla-security",
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
