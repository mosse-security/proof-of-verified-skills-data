from __future__ import annotations

import json
import re
from pathlib import Path

from endorsement_scraper.enrichment import EnricherContext, EnrichmentResult, write_json_zip


def collect_youtube(context: EnricherContext, *, assessor_id: str, enricher_id: str) -> EnrichmentResult:
    document = json.loads((context.assessors_directory / f"{assessor_id}.json").read_text(encoding="utf-8"))
    links = document.get("links", {})
    urls = []
    for key in ("youtubeUrl", "youtubePlaylistUrl"):
        if isinstance(links.get(key), str):
            urls.append(_video_source_url(links[key]))
    if isinstance(links.get("youtubePlaylistUrls"), list):
        urls.extend(_video_source_url(url) for url in links["youtubePlaylistUrls"] if isinstance(url, str))
    if not urls:
        raise ValueError(f"{assessor_id} must define a YouTube URL or playlist URL")
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("Install yt-dlp to run YouTube enrichers") from exc
    records = []
    options = {"extract_flat": True, "skip_download": True, "quiet": True, "ignoreerrors": True, "playlistend": context.playlist_end or None}
    with yt_dlp.YoutubeDL(options) as client:
        for source in urls:
            info = client.extract_info(source, download=False)
            if not isinstance(info, dict):
                continue
            entries = info.get("entries") or [info]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                video_id = entry.get("id")
                title = entry.get("title")
                if not isinstance(title, str) or not title.strip():
                    continue
                url = entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
                if not isinstance(url, str):
                    continue
                records.append({"assessor-id": assessor_id, "title": title.strip(), "url": url, "video-id": video_id, "conference": _year(title), "source": source, "upload-date": entry.get("upload_date"), "description": entry.get("description"), "channel": entry.get("channel") or entry.get("uploader")})
    unique = {(r["url"]): r for r in records}
    if not unique:
        raise RuntimeError(f"yt-dlp returned no {assessor_id} videos")
    return write_json_zip(context.output_directory / enricher_id / "data.zip", list(unique.values()), overwrite=context.overwrite)


def _year(value: str) -> str | None:
    match = re.search(r"\b(20\d{2})\b", value)
    return match.group(1) if match else None


def _video_source_url(value: str) -> str:
    """Turn a channel home URL into its uploads feed; preserve playlists."""

    value = value.strip()
    if "youtube.com/" in value and "/playlist" not in value and not re.search(r"/(?:videos|streams|shorts)(?:[/?#]|$)", value):
        return value.rstrip("/") + "/videos"
    return value
