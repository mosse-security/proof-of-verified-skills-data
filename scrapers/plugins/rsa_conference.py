from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.rsa_conference import RsaConferenceScraper


class RsaConferenceArchiveScraper(BaseCollectionScraper):
    assessor_id = "rsa-conference"
    scraper_id = "rsa-conference-agenda"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = RsaConferenceScraper(
            assessor_file=context.assessors_directory / "rsa-conference" / "rsa-conference.json",
            html_directory=context.html_directory / "rsa-conference",
            output_directory=context.output_directory / "rsa-conference",
            profile_directory=context.profile_directory / "rsa-conference",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout,
            retries=context.retries,
            backoff=context.backoff,
            delay=context.delay,
            user_agent=context.user_agent,
        ).run()
        return CollectionScraperResult(
            pages=len(results),
            endorsements=sum(item.endorsements for item in results),
            created=len(results),
            output_files=tuple(item.output for item in results),
        )
