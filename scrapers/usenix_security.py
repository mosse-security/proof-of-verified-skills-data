from __future__ import annotations

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.usenix_security import UsenixSecurityScraper


class UsenixSecurityArchiveScraper(BaseCollectionScraper):
    assessor_id = "usenix-security"
    scraper_id = "usenix-security-papers"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = UsenixSecurityScraper(
            assessor_file=context.assessors_directory / "usenix-security.json",
            html_directory=context.html_directory / "usenix-security.zip",
            output_directory=context.output_directory / "usenix-security",
            profile_directory=context.profile_directory / "usenix-security",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
