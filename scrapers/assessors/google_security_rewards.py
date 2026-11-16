"""Google Bug Hunters leaderboard scraper backed by the public REST endpoint."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from ..archives import ArchiveStore
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


DEFAULT_ENDPOINT = "https://bughunters.google.com/rest/v1/profiles/search"
LEADERBOARD_URL = "https://bughunters.google.com/leaderboard"


@dataclass(frozen=True, slots=True)
class GoogleLeaderboardResult:
    page: int
    endorsements: int
    output: Path


class GoogleSecurityRewardsScraper:
    assessor_id = "google-security-rewards"
    scraper_id = "google-bug-hunters-leaderboard"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/google-security-rewards/google-security-rewards.json"),
        archive_file: Path = Path("data/archives/html/google-security-rewards.zip"),
        output_directory: Path = Path("tmp/endorsements/google-security-rewards"),
        profile_directory: Path = Path("tmp/profiles/google-security-rewards"),
        overwrite: bool = True,
        timeout: float = 30,
        retries: int = 2,
    ) -> None:
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.archive = ArchiveStore(Path(archive_file).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        links = json.loads(self.assessor_file.read_text(encoding="utf-8")).get("links", {})
        self.endpoint = links.get("leaderboardEndpoint", DEFAULT_ENDPOINT)
        self.fetch = HttpClient(
            assessor_id=self.assessor_id,
            scraper_id=self.scraper_id,
            timeout=timeout,
            retries=retries,
        ).fetch

    def run(self) -> list[GoogleLeaderboardResult]:
        results: list[GoogleLeaderboardResult] = []
        page = 0
        expected_outputs: set[Path] = set()
        while True:
            request_url = self._page_url(page)
            member = f"leaderboard/page-{page:04d}.json"
            body = self.archive.read(member)
            if body is None or self.overwrite:
                response = self.fetch(Request(request_url, headers={"Accept": "application/json"}))
                if response.status != 200:
                    raise RuntimeError(f"Google leaderboard returned HTTP {response.status}")
                body = response.body
                self.archive.write(member, body)
            document = json.loads(body.decode("utf-8"))
            items = document.get("items", [])
            if not items:
                break
            records = [self._record(item) for item in items]
            output = self.output_directory / f"google-bug-hunters-page-{page:04d}.json"
            profile_output = self.profile_directory / f"google-bug-hunters-page-{page:04d}.json"
            expected_outputs.add(output)
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = [{"name": item["name"], "biography": "", "contact": self._contacts(item)} for item in items]
            if self.overwrite or not profile_output.exists():
                profile_output.parent.mkdir(parents=True, exist_ok=True)
                profile_output.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(GoogleLeaderboardResult(page, len(records), output))
            page += 1
            if page * 60 >= int(document.get("totalCount", 0)):
                break
        for stale in self.output_directory.glob("*.json"):
            if stale not in expected_outputs:
                stale.unlink(missing_ok=True)
        return results

    def _page_url(self, page: int) -> str:
        return self.endpoint + "?" + urlencode({
            "config": "hof_all", "country": "", "list": "HOF", "order": "ASC",
            "pageIndex": page, "pageSize": 60, "query": "", "sort": "RANK",
        })

    def _record(self, item: dict) -> dict:
        name = str(item.get("name", "")).strip()
        rank = item.get("rank", "")
        country = item.get("country") or "unknown"
        joined = str(item.get("joined", ""))[:10]
        parsed_year = int(joined[:4]) if joined[:4].isdigit() else 0
        year = parsed_year if 1000 <= parsed_year <= 9999 else 2026
        awards = item.get("awards") or []
        description = f"Ranked #{rank} on the Google Bug Hunters leaderboard ({country}); member since {joined or 'unknown'}. Public profile records {len(awards)} awards."
        return build_endorsement_record(
            name=name,
            label="Google Bug Hunters Leaderboard",
            subtitle="Hall of Fame",
            description=description,
            endorsement_type="recognition",
            assessor=self.assessor,
            url=LEADERBOARD_URL,
            year=year,
            domains=("vulnerability-research",),
            evidence_links=({"url": LEADERBOARD_URL, "title": "Google Bug Hunters leaderboard"},),
        )

    @staticmethod
    def _contacts(item: dict) -> list[dict[str, str]]:
        website = item.get("website")
        return [{"label": "Website", "url": str(website)}] if website else []
