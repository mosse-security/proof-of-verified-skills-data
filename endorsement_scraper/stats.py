"""Operator-facing run statistics and sanity checks."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runner import RunReport


def build_run_stats(report: RunReport, *, started_at: datetime, finished_at: datetime | None = None) -> dict[str, Any]:
    finished_at = finished_at or datetime.now(timezone.utc)
    totals = report.totals()
    scrapers = []
    for item in report.scrapers:
        scrapers.append({
            "scraper-id": item.scraper_id,
            "assessor-id": item.assessor_id,
            "pages": item.pages,
            "endorsements": item.endorsements,
            "created": item.created,
            "skipped": item.skipped,
            "overwritten": item.overwritten,
            "error": item.error,
        })
    validations = []
    for item in report.scrapers:
        if item.assessor_id == "def-con":
            validations.append({
                "name": "def-con-endorsements-nonzero",
                "passed": item.endorsements > 0 and item.error is None,
                "actual": item.endorsements,
                "minimum": 1,
            })
    return {
        "last-run": finished_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "started-at": started_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "duration-seconds": round((finished_at - started_at).total_seconds(), 3),
        "status": "ok" if not report.failed and all(item["passed"] for item in validations) else "failed",
        "scrapers": scrapers,
        "totals": totals,
        "validations": validations,
    }


def validate_run_stats(stats: dict[str, Any]) -> None:
    if not isinstance(stats, dict):
        raise ValueError("stats must be an object")
    if stats.get("status") not in {"ok", "failed"}:
        raise ValueError("stats.status must be ok or failed")
    if not isinstance(stats.get("last-run"), str) or not stats["last-run"].endswith("Z"):
        raise ValueError("stats.last-run must be a UTC timestamp")
    scrapers = stats.get("scrapers")
    if not isinstance(scrapers, list):
        raise ValueError("stats.scrapers must be an array")
    for item in scrapers:
        if not isinstance(item, dict) or not isinstance(item.get("endorsements"), int):
            raise ValueError("each scraper stat must include an endorsement count")


def write_run_stats(path: Path, stats: dict[str, Any]) -> None:
    validate_run_stats(stats)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False, mode="w", encoding="utf-8") as temporary:
            json.dump(stats, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
