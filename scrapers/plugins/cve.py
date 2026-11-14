from __future__ import annotations

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.cve import CveScraper


class CveCollectionScraper(BaseCollectionScraper):
    assessor_id = "mitre"
    scraper_id = "cve-records"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        result = CveScraper(
            assessor_file=context.assessors_directory / "mitre" / "mitre.json",
            output_directory=context.output_directory / "mitre",
            profile_directory=context.profile_directory / "mitre",
            overwrite=context.overwrite if context.overwrite is not None else True,
        ).run()
        return CollectionScraperResult(
            pages=result.cve_files,
            endorsements=result.records,
            created=1,
            output_files=(result.output,),
        )
