from __future__ import annotations

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.layer_one import LayerOneScraper


class LayerOneArchiveScraper(BaseCollectionScraper):
    assessor_id = "layer-one"
    scraper_id = "layer-one-speakers"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        results = LayerOneScraper(
            assessor_file=context.assessors_directory / "layer-one.json",
            html_directory=context.html_directory / "layer-one.zip",
            output_directory=context.output_directory / "layer-one",
            profile_directory=context.profile_directory / "layer-one",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout, retries=context.retries,
        ).run()
        return CollectionScraperResult(
            pages=len(results), endorsements=sum(r.endorsements for r in results),
            created=len(results), output_files=tuple(r.output for r in results),
        )
