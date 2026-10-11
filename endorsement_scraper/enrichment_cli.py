from __future__ import annotations

import argparse
import os
from pathlib import Path

from .enrichment import EnricherContext, EnrichmentError, discover_enrichers, run_enrichers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="enrich-endorsements")
    parser.add_argument("--enrichers-dir", type=Path, default=Path("enrichers"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/enrichments"))
    parser.add_argument("--assessors-dir", type=Path, default=Path("data/assessors"))
    parser.add_argument("--enricher", action="append", dest="enricher_ids")
    parser.add_argument("--workers", type=int, default=min(32, (os.cpu_count() or 1) + 4))
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--playlist-end", type=int, default=0, help="Limit playlist entries (0 means all).")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    try:
        classes = discover_enrichers(args.enrichers_dir)
    except EnrichmentError as exc:
        parser.error(str(exc))
    selected = [item for item in classes if not args.enricher_ids or item.enricher_id in args.enricher_ids]
    if args.list:
        for item in selected:
            print(item.enricher_id)
        return 0
    if not selected:
        parser.error("No enrichers matched")
    results = run_enrichers(
        selected,
        EnricherContext(args.output_dir, args.assessors_dir, args.overwrite, args.playlist_end),
        args.workers,
    )
    for result in results:
        print(f"{result.status:10} {result.enricher_id}: records={result.records} output={result.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
