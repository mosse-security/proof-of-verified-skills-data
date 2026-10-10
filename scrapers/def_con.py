from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from endorsement_scraper import (
    BaseCollectionScraper,
    CollectionScraperContext,
    CollectionScraperResult,
)
from endorsement_scraper.assessors.def_con import DefConScraper


class DefConArchiveScraper(BaseCollectionScraper):
    """Plugin adapter used by the unified scraper runner."""

    assessor_id = "def-con"
    scraper_id = "def-con-speakers"
    overwrite_by_default = True

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        overwrite = (
            self.overwrite_by_default
            if context.overwrite is None
            else context.overwrite
        )
        results = DefConScraper(
            assessor_file=(
                context.assessors_directory / f"{self.assessor_id}.json"
            ),
            html_directory=(
                context.html_directory / f"{self.assessor_id}.zip"
                if (context.html_directory / f"{self.assessor_id}.zip").exists()
                else context.html_directory / self.assessor_id
            ),
            output_directory=context.output_directory / self.assessor_id,
            profile_directory=context.profile_directory / self.assessor_id,
            workers=context.workers,
            overwrite=overwrite,
            timeout=context.timeout,
            retries=context.retries,
            backoff=context.backoff,
            delay=context.delay,
            user_agent=context.user_agent,
        ).run()
        statuses = [result.status for result in results]
        return CollectionScraperResult(
            pages=len(results),
            endorsements=sum(result.endorsements for result in results),
            created=statuses.count("created"),
            skipped=statuses.count("skipped"),
            overwritten=statuses.count("overwritten"),
            output_files=tuple(result.output for result in results),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse cached DEF CON speaker pages, fetching missing pages."
    )
    parser.add_argument(
        "--assessor-file",
        type=Path,
        default=Path("data/assessors/def-con.json"),
    )
    parser.add_argument(
        "--html-dir", type=Path, default=Path("data/archives/html/def-con.zip")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/tmp/endorsements/def-con")
    )
    parser.add_argument(
        "--profile-dir", type=Path, default=Path("data/tmp/profiles/def-con")
    )
    parser.add_argument(
        "--workers", type=int, default=min(32, (os.cpu_count() or 1) + 4)
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Keep an existing conference JSON file instead of replacing it.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scraper = DefConScraper(
        assessor_file=args.assessor_file,
        html_directory=args.html_dir,
        output_directory=args.output_dir,
        profile_directory=args.profile_dir,
        workers=args.workers,
        overwrite=not args.no_overwrite,
    )
    try:
        results = scraper.run()
    except Exception as exc:
        print(f"DEF CON scraper failed: {exc}", file=sys.stderr)
        return 1
    for result in results:
        print(
            f"DEF CON {result.year}: {result.endorsements} endorsements, "
            f"HTML={result.cache}, output={result.status} ({result.output})"
        )
    print(
        f"Total: {sum(result.endorsements for result in results)} endorsements "
        f"across {len(results)} conferences"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


