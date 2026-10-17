from __future__ import annotations

import argparse
import os
from pathlib import Path

from scrapers import BaseCollectionScraper, CollectionScraperContext, CollectionScraperResult
from scrapers.assessors.black_hat import BlackHatScraper


class BlackHatArchiveScraper(BaseCollectionScraper):
    assessor_id = "black-hat"
    scraper_id = "black-hat-briefings"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        archive = context.html_directory / "black-hat.zip"
        scraper = BlackHatScraper(
            assessor_file=context.assessors_directory / "black-hat" / "black-hat.json",
            html_directory=archive if archive.exists() else context.html_directory / "black-hat",
            output_directory=context.output_directory / "black-hat",
            profile_directory=context.profile_directory / "black-hat",
            overwrite=context.overwrite if context.overwrite is not None else True,
            timeout=context.timeout,
            retries=context.retries,
            backoff=context.backoff,
            delay=context.delay,
            user_agent=context.user_agent,
        )
        results = scraper.run()
        return CollectionScraperResult(
            pages=len(results),
            endorsements=sum(item.endorsements for item in results),
            created=sum(1 for item in results if item.output.exists()),
            output_files=tuple(item.output for item in results),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse archived Black Hat briefing pages")
    parser.add_argument("--no-overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=min(32, (os.cpu_count() or 1) + 4))
    args = parser.parse_args(argv)
    context = CollectionScraperContext(
        assessors_directory=Path("data/assessors"),
        output_directory=Path("tmp/endorsements"),
        html_directory=Path("data/archives/html"),
        profile_directory=Path("tmp/profiles"),
        workers=args.workers,
        overwrite=not args.no_overwrite,
        timeout=30,
        retries=2,
        backoff=0.5,
        delay=0,
        user_agent="verified-endorsement-scraper/0.1",
    )
    result = BlackHatArchiveScraper().run(context)
    print(f"Black Hat: {result.endorsements} endorsements across {result.pages} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



