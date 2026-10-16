from __future__ import annotations

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.acm_ccs import AcmCcsScraper


class AcmCcsArchiveScraper(BaseCollectionScraper):
    assessor_id = "acm-ccs"
    scraper_id = "acm-ccs-accepted-papers"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = AcmCcsScraper(
            assessor_file=context.assessors_directory / "acm-ccs.json",
            html_directory=context.html_directory / "acm-ccs.zip",
            output_directory=context.output_directory / "acm-ccs",
            profile_directory=context.profile_directory / "acm-ccs",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
