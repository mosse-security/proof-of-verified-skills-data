from __future__ import annotations

import argparse
import os
from pathlib import Path

from endorsement_scraper import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from endorsement_scraper.assessors.cansecwest import CanSecWestScraper


class CanSecWestArchiveScraper(BaseCollectionScraper):
    assessor_id = "cansecwest"
    scraper_id = "cansecwest-presentations"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        scraper = CanSecWestScraper(
            assessor_file=context.assessors_directory / "cansecwest.json",
            html_directory=context.html_directory / "cansecwest.zip",
            output_directory=context.output_directory / "cansecwest",
            profile_directory=context.profile_directory / "cansecwest",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout,
            retries=context.retries,
        )
        results = scraper.run()
        return CollectionScraperResult(pages=len(results), endorsements=sum(r.endorsements for r in results), created=len(results), output_files=tuple(r.output for r in results))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse archived CanSecWest presentation pages")
    parser.add_argument("--no-overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=min(32, (os.cpu_count() or 1) + 4))
    args = parser.parse_args(argv)
    context = CollectionScraperContext(assessors_directory=Path("data/assessors"), output_directory=Path("data/tmp/endorsements"), html_directory=Path("data/archives/html"), profile_directory=Path("data/tmp/profiles"), workers=args.workers, overwrite=not args.no_overwrite, timeout=30, retries=2, backoff=0.5, delay=0, user_agent="verified-endorsement-scraper/0.1")
    result = CanSecWestArchiveScraper().run(context)
    print(f"CanSecWest: {result.endorsements} endorsements across {result.pages} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
