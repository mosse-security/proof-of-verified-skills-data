from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .archives import ArchiveStore


def archive_assessor(
    assessor_id: str,
    *,
    assessors_directory: Path = Path("data/assessors"),
    output_directory: Path = Path("data/archives/html"),
    overwrite: bool = False,
    timeout: float = 30,
    retries: int = 2,
) -> tuple[int, int, list[str]]:
    assessor_path = assessors_directory / assessor_id / f"{assessor_id}.json"
    document = json.loads(assessor_path.read_text(encoding="utf-8"))
    urls = document.get("links", {}).get("processUrls", [])
    if not isinstance(urls, list) or not urls:
        raise ValueError(f"{assessor_path} must contain links.processUrls")
    archive_path = output_directory / f"{assessor_id}.zip"
    store = ArchiveStore(archive_path)
    fetched = skipped = 0
    failures: list[str] = []
    for url in urls:
        member = _member_name(url)
        if not overwrite and store.read(member) is not None:
            skipped += 1
            continue
        body = None
        error = None
        for attempt in range(retries + 1):
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    body = response.read()
                break
            except (OSError, urllib.error.URLError) as exc:
                error = exc
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
        if body is None:
            failures.append(f"{url}: {error}")
            continue
        store.write(member, body)
        fetched += 1
    return fetched, skipped, failures


def _member_name(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.strip("/") or "index.html"
    if path.endswith("/"):
        path += "index.html"
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archive-assessor")
    parser.add_argument("--assessor", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args(argv)
    fetched, skipped, failures = archive_assessor(
        args.assessor,
        overwrite=args.overwrite,
        timeout=args.timeout,
        retries=args.retries,
    )
    print(f"{args.assessor}: fetched={fetched} skipped={skipped} failed={len(failures)}")
    for failure in failures:
        print(f"FAILED {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
