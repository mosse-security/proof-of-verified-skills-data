from __future__ import annotations

import json
import logging
import os
import random
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping

from .models import Request, Response


LOGGER = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


class HttpClient:
    """Small HTTP client with retry, throttling, and optional snapshots."""

    def __init__(
        self,
        *,
        organization_id: str,
        scraper_id: str,
        timeout: float = 30,
        retries: int = 2,
        backoff: float = 0.5,
        delay: float = 0,
        user_agent: str = "verified-endorsement-scraper/0.1",
        save_html: bool = False,
        html_directory: Path = Path("data/html"),
    ) -> None:
        self.organization_id = organization_id
        self.scraper_id = scraper_id
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.delay = delay
        self.user_agent = user_agent
        self.save_html = save_html
        self.html_directory = html_directory
        self._last_request_at = 0.0

    def fetch(self, request: Request) -> Response:
        headers = {"User-Agent": self.user_agent, **dict(request.headers)}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._throttle()
            try:
                raw_request = urllib.request.Request(
                    request.url,
                    data=request.body,
                    headers=headers,
                    method=request.method.upper(),
                )
                with urllib.request.urlopen(raw_request, timeout=self.timeout) as result:
                    response = Response(
                        request=request,
                        url=result.geturl(),
                        status=result.status,
                        headers=dict(result.headers.items()),
                        body=result.read(),
                    )
                if self.save_html:
                    self._save_snapshot(response)
                return response
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                sleep_for = self.backoff * (2**attempt) + random.random() * 0.1
                LOGGER.warning(
                    "Fetch failed for %s (attempt %d/%d); retrying in %.2fs: %s",
                    request.url,
                    attempt + 1,
                    self.retries + 1,
                    sleep_for,
                    exc,
                )
                time.sleep(sleep_for)
        raise FetchError(f"Failed to fetch {request.url}: {last_error}") from last_error

    def _throttle(self) -> None:
        remaining = self.delay - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _save_snapshot(self, response: Response) -> None:
        directory = (
            self.html_directory / self.organization_id / self.scraper_id
        )
        directory.mkdir(parents=True, exist_ok=True)
        stem = response.request.fingerprint
        _atomic_write(directory / f"{stem}.html", response.body)
        metadata = {
            "requestedUrl": response.request.url,
            "finalUrl": response.url,
            "status": response.status,
            "fetchedAt": response.fetched_at,
            "headers": dict(response.headers),
        }
        _atomic_write(
            directory / f"{stem}.json",
            (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode(),
        )


def _atomic_write(path: Path, content: bytes) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(content)
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)

