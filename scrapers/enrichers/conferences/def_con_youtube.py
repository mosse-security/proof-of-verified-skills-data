from __future__ import annotations

import json
from pathlib import Path

from scrapers.enrichment import BaseEnricher, EnricherContext, EnrichmentResult, write_json_zip


class DefConYouTubeRecordings(BaseEnricher):
    enricher_id = "def-con-youtube-recordings"

    def run(self, context: EnricherContext) -> EnrichmentResult:
        assessor_path = context.assessors_directory / "def-con" / "def-con.json"
        document = json.loads(assessor_path.read_text(encoding="utf-8"))
        youtube_url = document.get("links", {}).get("youtubeUrl")
        if not isinstance(youtube_url, str) or not youtube_url:
            raise ValueError(f"{assessor_path} must define links.youtubeUrl")
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("Install yt-dlp to run the DEF CON YouTube enricher") from exc
        options = {
            "extract_flat": True,
            "skip_download": True,
            "quiet": True,
            "ignoreerrors": True,
            "playlistend": context.playlist_end or None,
        }
        with yt_dlp.YoutubeDL(options) as client:
            info = client.extract_info(youtube_url, download=False)
        if not isinstance(info, dict):
            raise RuntimeError("yt-dlp returned no DEF CON YouTube channel data")
        entries = info.get("entries", []) if isinstance(info, dict) else []
        records = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            video_id = entry.get("id")
            url = entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
            title = entry.get("title")
            if not isinstance(title, str) or not isinstance(url, str):
                continue
            records.append({
                "assessor-id": "def-con",
                "title": title,
                "url": url,
                "conference": _conference_number(title),
                "video-id": video_id,
                "upload-date": entry.get("upload_date"),
                "description": entry.get("description"),
                "channel": entry.get("channel") or entry.get("uploader"),
            })
        if not records:
            raise RuntimeError("yt-dlp returned no DEF CON YouTube videos")
        return write_json_zip(context.output_directory / self.enricher_id / "data.zip", records, overwrite=context.overwrite)


def _conference_number(value: str) -> str | None:
    import re
    match = re.search(r"(?:def\s*con|defcon)[^0-9]{0,4}(\d{1,2})", value.casefold())
    return match.group(1) if match else None
