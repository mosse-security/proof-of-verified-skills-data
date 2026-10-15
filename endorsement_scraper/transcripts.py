"""Download and archive English YouTube transcripts for endorsement videos."""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import tempfile
import zipfile
import os
import time
from pathlib import Path
from typing import Any

from .logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def load_video_catalog(assessor_id: str, *, enrichments_directory: Path = Path("data/enrichments")) -> list[dict[str, Any]]:
    path = enrichments_directory / f"{assessor_id}-youtube-recordings" / "data.zip"
    if not path.is_file():
        raise FileNotFoundError(f"Missing YouTube enrichment archive: {path}")
    with zipfile.ZipFile(path) as archive:
        records = json.loads(archive.read("data.json"))
    if not isinstance(records, list):
        raise ValueError(f"{path}!data.json must contain an array")
    return [record for record in records if isinstance(record, dict) and record.get("url")]


def archive_transcripts(
    assessor_id: str,
    *,
    archived_directory: Path = Path("data/archives/yt-transcripts"),
    enrichments_directory: Path = Path("data/enrichments"),
    overwrite: bool = False,
    playlist_end: int = 0,
    matched_only: bool = False,
    video_ids: set[str] | None = None,
) -> dict[str, int]:
    """Archive new or changed English transcripts without duplicating videos."""
    records = load_video_catalog(assessor_id, enrichments_directory=enrichments_directory)
    if matched_only:
        captured = _captured_video_ids(assessor_id)
        records = [record for record in records if str(record.get("video-id") or _video_id(str(record.get("url", "")))) in captured]
    if video_ids:
        records = [record for record in records if str(record.get("video-id") or _video_id(str(record.get("url", "")))) in video_ids]
    LOGGER.info("Starting transcript archive for %s: catalog=%d", assessor_id, len(records))
    archive_path = archived_directory / f"{assessor_id}-transcripts.zip"
    existing_members, previous = _read_archive_state(archive_path)
    pending: dict[str, bytes] = {}
    current: list[dict[str, Any]] = []
    counters = {"catalog": len(records), "downloaded": 0, "skipped": 0, "no_subtitles": 0, "failed": 0}
    with tempfile.TemporaryDirectory(prefix="transcripts-") as temporary:
        client = _make_client(temporary)
        for index, record in enumerate(records):
            if playlist_end and index >= playlist_end:
                break
            video_id = str(record.get("video-id") or _video_id(str(record["url"])))
            if not video_id:
                counters["failed"] += 1
                continue
            member = f"transcripts/{video_id}.txt"
            fingerprint = {"video-id": video_id, "url": str(record["url"]), "title": str(record.get("title", ""))}
            existing = previous.get(video_id)
            existing_member = member in existing_members or member in pending
            unchanged = existing is not None and all(
                existing.get(key) == value for key, value in fingerprint.items()
            )
            if not overwrite and existing_member and (existing is None or unchanged):
                counters["skipped"] += 1
                current.append({**fingerprint, "status": "archived"})
                continue
            try:
                transcript = _download_transcript(str(record["url"]), client, temporary)
            except Exception:
                LOGGER.exception("Transcript download failed for %s (%s)", video_id, record["url"])
                counters["failed"] += 1
                current.append({**fingerprint, "status": "failed"})
                continue
            if not transcript:
                LOGGER.warning("No English subtitles available for %s (%s)", video_id, record["url"])
                counters["no_subtitles"] += 1
                current.append({**fingerprint, "status": "no_subtitles"})
                continue
            pending[member] = transcript.encode("utf-8")
            counters["downloaded"] += 1
            current.append({**fingerprint, "status": "archived"})
            if len(current) % 10 == 0:
                _write_checkpoint(archive_path, pending, assessor_id, current)
                existing_members.update(pending)
                pending.clear()
                LOGGER.info("Checkpoint for %s: processed=%d downloaded=%d skipped=%d no_subtitles=%d failed=%d", assessor_id, len(current), counters["downloaded"], counters["skipped"], counters["no_subtitles"], counters["failed"])
    _write_checkpoint(archive_path, pending, assessor_id, current)
    LOGGER.info("Finished transcript archive for %s: %s", assessor_id, counters)
    return counters


def _make_client(temporary: str):
    import yt_dlp
    options = {
        "skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
        "subtitleslangs": ["en.*"], "subtitlesformat": "vtt",
        "outtmpl": str(Path(temporary) / "video.%(ext)s"), "quiet": True,
        "no_warnings": True, "ignoreerrors": False, "retries": 3,
        "fragment_retries": 3, "sleep_interval_requests": 1, "noprogress": True,
    }
    return yt_dlp.YoutubeDL(options)


def _download_transcript(url: str, client, temporary: str) -> str:
    for old in Path(temporary).glob("*.vtt"):
        old.unlink(missing_ok=True)
    client.download([url])
    subtitle_files = sorted(Path(temporary).glob("*.vtt"))
    if not subtitle_files:
        return ""
    text = _clean_vtt(subtitle_files[0].read_text(encoding="utf-8", errors="replace"))
    for subtitle_file in subtitle_files:
        subtitle_file.unlink(missing_ok=True)
    return text


def _read_archive_state(path: Path) -> tuple[set[str], dict[str, dict[str, Any]]]:
    if not path.is_file():
        return set(), {}
    with zipfile.ZipFile(path) as archive:
        members = set(archive.namelist())
        if "manifest.json" not in members:
            return members, {}
        manifest = json.loads(archive.read("manifest.json"))
    return members, {str(item.get("video-id")): item for item in manifest.get("videos", [])}


def _write_checkpoint(path: Path, pending: dict[str, bytes], assessor_id: str, videos: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        historical: dict[str, dict[str, Any]] = {}
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
            if path.is_file():
                with zipfile.ZipFile(path) as source:
                    if "manifest.json" in source.namelist():
                        old_manifest = json.loads(source.read("manifest.json"))
                        historical = {str(item.get("video-id")): item for item in old_manifest.get("videos", []) if item.get("video-id")}
                    for info in source.infolist():
                        if info.filename not in pending and info.filename != "manifest.json":
                            target.writestr(info, source.read(info.filename))
            for member, content in pending.items():
                target.writestr(member, content)
        historical.update({str(item["video-id"]): item for item in videos if item.get("video-id")})
        manifest = {"assessor-id": assessor_id, "videos": sorted(historical.values(), key=lambda item: str(item.get("video-id", "")))}
        target_manifest = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with zipfile.ZipFile(temporary, "a", zipfile.ZIP_DEFLATED) as target:
            target.writestr("manifest.json", target_manifest)
        for attempt in range(10):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.5 * (attempt + 1))
    finally:
        Path(temporary).unlink(missing_ok=True)


def _clean_vtt(text: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line in {"WEBVTT", "STYLE", "KIND", "LANGUAGE"} or line.startswith(("NOTE", "STYLE", "##")):
            continue
        if "-->" in line or re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def _video_id(url: str) -> str:
    match = re.search(r"[?&]v=([\w-]{6,})", url)
    return match.group(1) if match else ""


def _captured_video_ids(assessor_id: str) -> set[str]:
    ids: set[str] = set()
    for path in Path("data/individuals").glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        for endorsement in document.get("endorsements", []):
            if endorsement.get("assessor-id") != assessor_id:
                continue
            for link in endorsement.get("evidence-links", []):
                video_id = _video_id(str(link.get("url", "")))
                if video_id:
                    ids.add(video_id)
    return ids


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="archive-transcripts")
    parser.add_argument("--assessor", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--playlist-end", type=int, default=0)
    parser.add_argument("--matched-only", action="store_true", help="Archive only videos linked to captured endorsements")
    parser.add_argument("--video-id", action="append", dest="video_ids", help="Restrict capture to a specific video ID (repeatable)")
    args = parser.parse_args(argv)
    result = archive_transcripts(args.assessor, overwrite=args.overwrite, playlist_end=args.playlist_end, matched_only=args.matched_only, video_ids=set(args.video_ids or []))
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    path = Path("data/archives/yt-transcripts") / f"{args.assessor}-transcripts.zip"
    print(f"archive={path} size={path.stat().st_size if path.exists() else 0}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
