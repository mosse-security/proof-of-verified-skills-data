from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .base import CollectionScraperContext
from .discovery import DiscoveryError, discover_all_scrapers
from .http import HttpClient
from .runner import CollectionScraperRunner, RunReport, ScraperRunner
from .storage import EndorsementStore, ProfileStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape-endorsements",
        description="Discover and run organization endorsement scrapers.",
    )
    parser.add_argument("--scrapers-dir", type=Path, default=Path("scrapers"))
    parser.add_argument(
        "--organizations-dir", type=Path, default=Path("data/organizations")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/endorsements"))
    parser.add_argument("--html-dir", type=Path, default=Path("data/html"))
    parser.add_argument("--profiles-dir", type=Path, default=Path("data/profiles"))
    parser.add_argument(
        "--organization",
        action="append",
        dest="organizations",
        metavar="ID",
        help="Run only this organization (repeatable).",
    )
    parser.add_argument(
        "--scraper",
        action="append",
        dest="scraper_ids",
        metavar="ID",
        help="Run only this scraper ID (repeatable).",
    )
    parser.add_argument("--workers", type=int, default=min(32, (os.cpu_count() or 1) + 4))
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1_000,
        help="Per-scraper safety limit; use 0 for unlimited (default: 1000).",
    )
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--backoff", type=float, default=0.5)
    parser.add_argument(
        "--delay",
        type=float,
        default=0,
        help="Minimum delay in seconds between requests from one scraper.",
    )
    parser.add_argument(
        "--user-agent", default="verified-endorsement-scraper/0.1"
    )
    parser.add_argument("--save-html", action="store_true")
    overwrite_group = parser.add_mutually_exclusive_group()
    overwrite_group.add_argument(
        "--overwrite",
        dest="overwrite",
        action="store_true",
        help="Rewrite existing output for every scraper.",
    )
    overwrite_group.add_argument(
        "--no-overwrite",
        dest="overwrite",
        action="store_false",
        help="Preserve existing output for every scraper.",
    )
    parser.set_defaults(overwrite=None)
    parser.add_argument("--list", action="store_true", help="List discovered scrapers.")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
    )
    try:
        discovered = discover_all_scrapers(args.scrapers_dir)
    except DiscoveryError as exc:
        print(f"Discovery error: {exc}", file=sys.stderr)
        return 2

    selected_pages = [
        cls
        for cls in discovered.page_scrapers
        if (not args.organizations or cls.organization_id in args.organizations)
        and (not args.scraper_ids or cls.scraper_id in args.scraper_ids)
    ]
    selected_collections = [
        cls
        for cls in discovered.collection_scrapers
        if (not args.organizations or cls.organization_id in args.organizations)
        and (not args.scraper_ids or cls.scraper_id in args.scraper_ids)
    ]
    if args.list:
        for cls in [*selected_pages, *selected_collections]:
            print(f"{cls.scraper_id}\t{cls.organization_id}\t{cls.__module__}.{cls.__name__}")
        return 0
    if not selected_pages and not selected_collections:
        print("No scrapers matched. Add a scraper or adjust the filters.", file=sys.stderr)
        return 2

    def client_factory(organization_id: str, scraper_id: str) -> HttpClient:
        return HttpClient(
            organization_id=organization_id,
            scraper_id=scraper_id,
            timeout=args.timeout,
            retries=args.retries,
            backoff=args.backoff,
            delay=args.delay,
            user_agent=args.user_agent,
            save_html=args.save_html,
            html_directory=args.html_dir,
        )

    runner = ScraperRunner(
        store=EndorsementStore(args.output_dir, args.organizations_dir),
        profile_store=ProfileStore(args.profiles_dir),
        client_factory=client_factory,
        workers=args.workers,
        overwrite=bool(args.overwrite),
        max_pages=None if args.max_pages == 0 else args.max_pages,
    )
    page_report = runner.run(selected_pages) if selected_pages else RunReport()
    collection_context = CollectionScraperContext(
        organizations_directory=args.organizations_dir,
        output_directory=args.output_dir,
        html_directory=args.html_dir,
        workers=args.workers,
        overwrite=args.overwrite,
        timeout=args.timeout,
        retries=args.retries,
        backoff=args.backoff,
        delay=args.delay,
        user_agent=args.user_agent,
        profile_directory=args.profiles_dir,
    )
    collection_report = (
        CollectionScraperRunner(
            context=collection_context, workers=args.workers
        ).run(selected_collections)
        if selected_collections
        else RunReport()
    )
    report = RunReport([*page_report.scrapers, *collection_report.scrapers])
    for item in report.scrapers:
        state = "FAILED" if item.error else "OK"
        print(
            f"{state:6} {item.scraper_id}: pages={item.pages} "
            f"endorsements={item.endorsements} created={item.created} "
            f"skipped={item.skipped} overwritten={item.overwritten}"
        )
        if item.error:
            print(f"       {item.error}", file=sys.stderr)
    totals = report.totals()
    print(
        f"Total: scrapers={len(report.scrapers)} pages={totals['pages']} "
        f"endorsements={totals['endorsements']} created={totals['created']} "
        f"skipped={totals['skipped']} overwritten={totals['overwritten']} "
        f"failed={len(report.failed)}"
    )
    return 1 if report.failed else 0
