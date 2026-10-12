from __future__ import annotations

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.blue_team_con import BlueTeamConScraper


class BlueTeamConArchiveScraper(BaseCollectionScraper):
    assessor_id = "blue-team-con"
    scraper_id = "blue-team-con-talks"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = BlueTeamConScraper(
            assessor_file=context.assessors_directory / "blue-team-con.json",
            html_directory=context.html_directory / "blue-team-con.zip",
            output_directory=context.output_directory / "blue-team-con",
            profile_directory=context.profile_directory / "blue-team-con",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
