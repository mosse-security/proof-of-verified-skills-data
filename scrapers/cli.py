from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .base import CollectionScraperContext
from .discovery import DiscoveryError, discover_all_scrapers
from .http import HttpClient
from .individuals import build_assessor_individuals
from .logging_config import configure_logging
from .runner import CollectionScraperRunner, RunReport, ScraperRunner
from .storage import EndorsementStore, ProfileStore
from .stats import build_run_stats, summarize_output, write_assessor_run_stats, write_run_stats
from .video_audit import audit_conference_video_matching


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape-endorsements",
        description="Discover and run assessor endorsement scrapers.",
    )
    parser.add_argument("--scrapers-dir", type=Path, default=Path("scrapers/plugins"))
    parser.add_argument(
        "--assessors-dir", type=Path, default=Path("data/assessors")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/endorsements"))
    parser.add_argument("--html-dir", type=Path, default=Path("data/archives/html"))
    parser.add_argument("--profiles-dir", type=Path, default=Path("tmp/profiles"))
    parser.add_argument("--stats-file", type=Path, default=Path("data/stats.json"))
    parser.add_argument(
        "--assessor",
        action="append",
        dest="assessors",
        metavar="ID",
        help="Run only this assessor (repeatable).",
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
    started_at = datetime.now(timezone.utc)
    configure_logging(level=getattr(logging, args.log_level))
    try:
        discovered = discover_all_scrapers(args.scrapers_dir)
    except DiscoveryError as exc:
        print(f"Discovery error: {exc}", file=sys.stderr)
        return 2

    selected_pages = [
        cls
        for cls in discovered.page_scrapers
        if (not args.assessors or cls.assessor_id in args.assessors)
        and (not args.scraper_ids or cls.scraper_id in args.scraper_ids)
    ]
    selected_collections = [
        cls
        for cls in discovered.collection_scrapers
        if (not args.assessors or cls.assessor_id in args.assessors)
        and (not args.scraper_ids or cls.scraper_id in args.scraper_ids)
    ]
    if args.list:
        for cls in [*selected_pages, *selected_collections]:
            print(f"{cls.scraper_id}\t{cls.assessor_id}\t{cls.__module__}.{cls.__name__}")
        return 0
    if not selected_pages and not selected_collections:
        print("No scrapers matched. Add a scraper or adjust the filters.", file=sys.stderr)
        return 2
    logging.getLogger(__name__).info(
        "Selected scrapers: page=%d collection=%d workers=%d",
        len(selected_pages), len(selected_collections), args.workers,
    )

    def client_factory(assessor_id: str, scraper_id: str) -> HttpClient:
        return HttpClient(
            assessor_id=assessor_id,
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
        store=EndorsementStore(args.output_dir, args.assessors_dir),
        profile_store=ProfileStore(args.profiles_dir),
        client_factory=client_factory,
        workers=args.workers,
        overwrite=bool(args.overwrite),
        max_pages=None if args.max_pages == 0 else args.max_pages,
    )
    page_report = runner.run(selected_pages) if selected_pages else RunReport()
    collection_context = CollectionScraperContext(
        assessors_directory=args.assessors_dir,
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
    # A failed scraper must not destroy its last successful local snapshot,
    # but successful assessors must still be rebuilt even if another scraper
    # in the same invocation failed.
    selected_assessors = {
        item.assessor_id for item in report.scrapers if not item.error
    }
    for assessor_id in sorted(selected_assessors):
        count = build_assessor_individuals(
            assessor_id,
            endorsements_directory=args.output_dir,
            profiles_directory=args.profiles_dir,
            assessors_directory=args.assessors_dir,
        )
        logging.getLogger(__name__).info(
            "Built assessor-local individuals: assessor=%s people=%s",
            assessor_id,
            count,
        )
    audit_conference_video_matching(
        assessors_directory=args.assessors_dir,
        output_directory=args.output_dir,
    )
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
    evidence_counts, domain_counts, subspecialty_counts, individual_count = summarize_output(
        args.output_dir
    )
    stats = build_run_stats(
        report,
        started_at=started_at,
        evidence_counts=evidence_counts,
        domain_counts=domain_counts,
        subspecialty_counts=subspecialty_counts,
        individual_count=individual_count,
    )
    write_run_stats(args.stats_file, stats)
    write_assessor_run_stats(args.assessors_dir, report, started_at=started_at)
    print(f"Stats: {args.stats_file} status={stats['status']} last-run={stats['last-run']}")
    logging.getLogger(__name__).info(
        "Scrape totals: pages=%d endorsements=%d failed=%d evidence=%d",
        totals["pages"], totals["endorsements"], len(report.failed),
        sum(stats.get("evidence", {}).values()) if isinstance(stats.get("evidence"), dict) else 0,
    )
    return 1 if report.failed else 0



