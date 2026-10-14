"""Audit YouTube coverage for conference endorsement outputs."""
from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


def audit_conference_video_matching(
    *,
    assessors_directory: Path,
    output_directory: Path,
    enrichments_directory: Path = Path("data/enrichments"),
) -> None:
    for assessor_path in sorted(assessors_directory.glob("*.json")):
        document = json.loads(assessor_path.read_text(encoding="utf-8"))
        if not str(document.get("category", "")).startswith("conference"):
            continue
        assessor_id = str(document.get("id", assessor_path.stem))
        enrichment_path = enrichments_directory / f"{assessor_id}-youtube-recordings" / "data.zip"
        if not enrichment_path.is_file():
            continue
        catalog = _catalog(enrichment_path)
        records = _records(output_directory / assessor_id)
        captured_ids = {
            video_id
            for record in records
            for link in record.get("evidence-links", [])
            for video_id in [_video_id(str(link.get("url", "")))]
            if video_id
        }
        unmatched = sorted(set(catalog) - captured_ids)
        without_video = [record for record in records if not any(
            _video_id(str(link.get("url", ""))) for link in record.get("evidence-links", [])
        )]
        if unmatched:
            LOGGER.warning(
                "%s YouTube videos are not matched to endorsements for %s; sample=%s",
                len(unmatched), assessor_id, ", ".join(unmatched[:5]),
            )
        if without_video:
            sample = ", ".join(str(record.get("label", "")) for record in without_video[:3])
            LOGGER.warning(
                "%s conference endorsements have no matched YouTube video for %s; sample=%s",
                len(without_video), assessor_id, sample,
            )


def _catalog(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        records = json.loads(archive.read("data.json"))
    return {video_id for record in records if (video_id := str(record.get("video-id") or _video_id(str(record.get("url", "")))))}


def _records(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not directory.is_dir():
        return records
    for path in directory.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            records.extend(record for record in payload if isinstance(record, dict))
    return records


def _video_id(url: str) -> str | None:
    match = re.search(r"[?&]v=([\w-]{6,})", url)
    return match.group(1) if match else None
