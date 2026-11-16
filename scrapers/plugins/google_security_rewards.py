from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.google_security_rewards import GoogleSecurityRewardsScraper


class GoogleBugHuntersLeaderboardScraper(BaseCollectionScraper):
    assessor_id = "google-security-rewards"
    scraper_id = "google-bug-hunters-leaderboard"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = GoogleSecurityRewardsScraper(
            assessor_file=context.assessors_directory / "google-security-rewards" / "google-security-rewards.json",
            archive_file=context.html_directory / "google-security-rewards.zip",
            output_directory=context.output_directory / "google-security-rewards",
            profile_directory=context.profile_directory / "google-security-rewards",
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
