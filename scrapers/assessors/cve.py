"""CVE record scraper with identity-registry gating."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from ..domains import detect_domains
from ..enrichment import EnrichmentCatalog
from ..identity_registry import IdentityRegistry, clean_person_name
from ..schema import AssessorMetadata, build_endorsement_record


_CVE_ID = re.compile(r"^CVE-(?P<year>20\d{2})-(?P<number>\d{4,})$", re.IGNORECASE)
_PERSON_KEY = re.compile(
    r"credit|author|finder|discover|report|research|acknowledg|submit|contact|analyst",
    re.IGNORECASE,
)
_NAME = re.compile(
    r"\b([A-Z][a-zÀ-ÖØ-öø-ÿ'’-]+(?:\s+[A-Z][a-zÀ-ÖØ-öø-ÿ'’-]+){1,3})\b"
)
_NAME_STOPWORDS = {
    "The", "This", "That", "For", "From", "Affected", "Product", "Security",
    "Remote", "Local", "National", "Common", "Vulnerability", "Research",
}


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    relationship: str
    field: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class CveRunResult:
    records: int
    people: int
    cve_files: int
    output: Path


class CveScraper:
    assessor_id = "mitre"
    scraper_id = "cve-records"
    repository = "https://github.com/CVEProject/cvelistV5.git"
    archive_url = "https://codeload.github.com/CVEProject/cvelistV5/zip/refs/heads/main"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/mitre/mitre.json"),
        output_directory: Path = Path("tmp/endorsements/mitre"),
        profile_directory: Path = Path("tmp/profiles/mitre"),
        review_directory: Path = Path("tmp/mitre"),
        source_directory: Path = Path("external/cvelistV5"),
        overwrite: bool = True,
    ) -> None:
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.review_directory = Path(review_directory)
        self.source_directory = Path(source_directory)
        self.overwrite = overwrite
        self.registry = IdentityRegistry.for_assessor(self.assessor_id)
        self.whitelist = self.registry._read(self.registry.global_whitelist_path)
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))

    def run(self) -> CveRunResult:
        """Process the CVE submodule checkout without copying its data."""

        if not self.source_directory.is_dir():
            raise FileNotFoundError(
                f"CVE repository checkout not found at {self.source_directory}. "
                "Initialize it with: git submodule update --init --depth 1 external/cvelistV5"
            )

        self.review_directory.mkdir(parents=True, exist_ok=True)
        review_path = self.review_directory / "individuals-review.jsonl"
        review_path.write_text("", encoding="utf-8")
        records, profiles, cve_files = self._process_checkout(self.source_directory, review_path)
        commit = self._git_commit(self.source_directory)

        self.review_directory.joinpath("source.json").write_text(
            json.dumps({"repository": self.repository, "commit": commit}, indent=2) + "\n",
            encoding="utf-8",
        )
        output = self.output_directory / "cve-records.json"
        if self.overwrite or not output.exists():
            self.output_directory.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(
                json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return CveRunResult(len(records), len(profiles), cve_files, output)

    def _process_checkout(
        self, source_directory: Path, review_path: Path
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        records: list[dict[str, Any]] = []
        people: dict[str, dict[str, Any]] = {}
        cve_files = 0
        with review_path.open("a", encoding="utf-8", newline="\n") as review:
            members = sorted(
                path for path in source_directory.rglob("CVE-*.json") if path.is_file()
            )
            for path in members:
                cve = self._read_cve_bytes(path.read_bytes())
                if cve is None:
                    continue
                cve_files += 1
                cve_id = str(cve.get("cveMetadata", {}).get("cveId", path.stem))
                match = _CVE_ID.match(cve_id)
                if not match:
                    continue
                candidates = list(_candidates(cve))
                candidates.extend(_whitelisted_mentions(cve, self.registry, self.whitelist))
                accepted: dict[str, Candidate] = {}
                for candidate in candidates:
                    decision = self.registry.decision(candidate.name)
                    if decision == "allow":
                        accepted.setdefault(self.registry.normalize(candidate.name), candidate)
                    elif decision == "unknown":
                        review.write(json.dumps({
                            "cve": cve_id,
                            "name": clean_person_name(candidate.name),
                            "relationship": candidate.relationship,
                            "field": candidate.field,
                            "excerpt": candidate.excerpt,
                        }, ensure_ascii=False) + "\n")
                        if cve_files % 100 == 0:
                            review.flush()
                description = _description(cve)
                url = f"https://www.cve.org/CVERecord?id={cve_id}"
                for candidate in accepted.values():
                    record = build_endorsement_record(
                        name=candidate.name,
                        label=cve_id,
                        description=description,
                        endorsement_type="vulnerability_discovery",
                        assessor=self.assessor,
                        subtitle=_subtitle(cve),
                        url=url,
                        year=int(match.group("year")),
                        domains=detect_domains(cve_id, description),
                        evidence_links=({"title": "CVE record", "url": url},),
                    )
                    records.append(record)
                    identity = self.registry.normalize(candidate.name)
                    people.setdefault(identity, {"name": clean_person_name(candidate.name), "biography": "", "contact": []})
        return records, list(people.values()), cve_files

    @staticmethod
    def _git_commit(source_directory: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_directory), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return "unknown"
        return result.stdout.strip() or "unknown"

    @staticmethod
    def _read_cve_bytes(content: bytes) -> dict[str, Any] | None:
        try:
            document = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return document if isinstance(document, dict) else None


def _candidates(document: dict[str, Any]) -> Iterator[Candidate]:
    def walk(value: Any, field: str = "") -> Iterator[Candidate]:
        if isinstance(value, dict):
            for key, child in value.items():
                child_field = f"{field}.{key}" if field else key
                if isinstance(child, str) and (
                    _PERSON_KEY.search(key) or _PERSON_KEY.search(child_field)
                ):
                    for name in _names_from_text(child):
                        yield Candidate(name, key.lower(), child_field, child[:400])
                else:
                    yield from walk(child, child_field)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child, field)
    yield from walk(document)


def _whitelisted_mentions(
    document: dict[str, Any], registry: IdentityRegistry, whitelist: Mapping[str, str]
) -> Iterator[Candidate]:
    text = json.dumps(document, ensure_ascii=False)
    seen: set[str] = set()
    for name in _names_from_text(text):
        normalized = registry.normalize(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        display = whitelist.get(normalized)
        if display:
            yield Candidate(display, "whitelist_match", "record", text[:400])


def _names_from_text(value: str) -> Iterator[str]:
    for match in _NAME.finditer(value):
        candidate = clean_person_name(match.group(1)).strip(" ,.;:()")
        if candidate and not any(part in _NAME_STOPWORDS for part in candidate.split()):
            yield candidate


def _description(document: dict[str, Any]) -> str:
    containers = document.get("containers", {})
    for container in (containers.get("cna", {}), containers.get("adp", {})):
        descriptions = container.get("descriptions", []) if isinstance(container, dict) else []
        for item in descriptions:
            if isinstance(item, dict) and item.get("value"):
                return str(item["value"])
    legacy = document.get("CVE_data_meta", {})
    return str(document.get("description", legacy.get("DESCRIPTION", "")))


def _subtitle(document: dict[str, Any]) -> str:
    """Render CVE and CVSS criticality using the existing subtitle field."""

    candidates: list[dict[str, Any]] = []
    containers = document.get("containers", {})
    if isinstance(containers, dict):
        for container in containers.values():
            if isinstance(container, dict):
                metrics = container.get("metrics", [])
                if isinstance(metrics, list):
                    candidates.extend(item for item in metrics if isinstance(item, dict))

    assessments: list[dict[str, Any]] = []
    for metric in candidates:
        for key, value in metric.items():
            if not key.lower().startswith("cvss") or not isinstance(value, dict):
                continue
            score = value.get("baseScore")
            severity = value.get("baseSeverity")
            if not isinstance(score, (int, float)) and not isinstance(severity, str):
                continue
            version = value.get("version")
            assessments.append({
                "severity": str(severity).upper() if severity else "UNKNOWN",
                "baseScore": score,
                "cvssVersion": str(version) if version else key.removeprefix("cvssV"),
                "vector": value.get("vectorString"),
            })

    if not assessments:
        return "CVE"
    severity_rank = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    strongest = max(
        assessments,
        key=lambda item: (
            float(item["baseScore"]) if isinstance(item["baseScore"], (int, float)) else -1,
            severity_rank.get(str(item["severity"]), -1),
        ),
    )
    score = strongest["baseScore"]
    score_text = f"{score:g}" if isinstance(score, (int, float)) else "n/a"
    return (
        f"CVE · Severity: {strongest['severity']} "
        f"(CVSS {strongest['cvssVersion']}, {score_text})"
    )
