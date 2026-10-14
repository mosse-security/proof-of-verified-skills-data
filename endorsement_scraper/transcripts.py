"""Download and archive English YouTube transcripts for endorsement videos."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .archives import ArchiveStore


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
) -> dict[str, int]:
    """Archive new or changed English transcripts without duplicating videos."""
    records = load_video_catalog(assessor_id, enrichments_directory=enrichments_directory)
    archive_path = archived_directory / f"{assessor_id}-transcripts.zip"
    store = ArchiveStore(archive_path)
    previous: dict[str, dict[str, Any]] = {}
    manifest_raw = store.read("manifest.json")
    if manifest_raw:
        previous = {str(item.get("video-id")): item for item in json.loads(manifest_raw).get("videos", [])}
    current: list[dict[str, Any]] = []
    counters = {"catalog": len(records), "downloaded": 0, "skipped": 0, "no_subtitles": 0, "failed": 0}
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
        if (
            not overwrite
            and existing is not None
            and all(existing.get(key) == value for key, value in fingerprint.items())
            and store.read(member) is not None
        ):
            counters["skipped"] += 1
            current.append({**fingerprint, "status": "archived"})
            continue
        try:
            transcript = _download_transcript(str(record["url"]))
        except Exception:
            counters["failed"] += 1
            current.append({**fingerprint, "status": "failed"})
            continue
        if not transcript:
            counters["no_subtitles"] += 1
            current.append({**fingerprint, "status": "no_subtitles"})
            continue
        store.write(member, transcript.encode("utf-8"))
        counters["downloaded"] += 1
        current.append({**fingerprint, "status": "archived"})
    manifest = {"assessor-id": assessor_id, "videos": current}
    store.write("manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return counters


def _download_transcript(url: str) -> str:
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("Install yt-dlp to archive transcripts") from exc
    with tempfile.TemporaryDirectory(prefix="transcripts-") as temporary:
        options = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en.*"],
            "subtitlesformat": "vtt",
            "outtmpl": str(Path(temporary) / "video.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
        }
        with yt_dlp.YoutubeDL(options) as client:
            client.download([url])
        subtitle_files = sorted(Path(temporary).glob("*.vtt"))
        if not subtitle_files:
            return ""
        return _clean_vtt(subtitle_files[0].read_text(encoding="utf-8", errors="replace"))


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archive-transcripts")
    parser.add_argument("--assessor", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--playlist-end", type=int, default=0)
    args = parser.parse_args(argv)
    result = archive_transcripts(args.assessor, overwrite=args.overwrite, playlist_end=args.playlist_end)
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    path = Path("data/archives/yt-transcripts") / f"{args.assessor}-transcripts.zip"
    print(f"archive={path} size={path.stat().st_size if path.exists() else 0}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
