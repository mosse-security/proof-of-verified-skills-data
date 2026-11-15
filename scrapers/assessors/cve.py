"""CVE record scraper with identity-registry gating."""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import date
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
        archive_directory: Path = Path("data/archives/cve"),
        year: int | None = None,
        overwrite: bool = True,
    ) -> None:
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.review_directory = Path(review_directory)
        self.source_directory = Path(source_directory)
        self.archive_directory = Path(archive_directory)
        self.year = year
        self.overwrite = overwrite
        self.registry = IdentityRegistry.for_assessor(self.assessor_id)
        self.whitelist = self.registry._read(self.registry.global_whitelist_path)
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))

    def run(self) -> CveRunResult:
        """Process the current CVE checkout with a text per-file ledger."""

        if not self.source_directory.is_dir():
            raise FileNotFoundError(
                f"CVE repository checkout not found at {self.source_directory}. "
                "Initialize it with: git submodule update --init --depth 1 external/cvelistV5"
            )

        self.review_directory.mkdir(parents=True, exist_ok=True)
        review_path = self.review_directory / "individuals-review.jsonl"
        commit = self._git_commit(self.source_directory)
        scan_directory = self.source_directory / "cves"
        if self.year is not None:
            scan_directory = scan_directory / str(self.year)
            if not scan_directory.is_dir():
                raise FileNotFoundError(
                    f"CVE year directory not found at {scan_directory}. "
                    "Select it with git sparse-checkout before running this year."
                )
        members = sorted(
            path for path in scan_directory.rglob("CVE-*.json") if path.is_file()
        )
        suffix = f"-{self.year}" if self.year is not None else ""
        processed_path = self.review_directory / f"processed-cves{suffix}.txt"
        output = self.output_directory / f"cve-records{suffix}.json"
        whitelist_signature = self.registry._signature(self.registry.global_whitelist_path)
        processed, resumable = self._read_processed_ledger(
            processed_path, commit, whitelist_signature, self.year
        )
        records = (
            self._read_json_array(
                output, self.archive_directory / output.with_suffix(".zip").name
            )
            if resumable
            else []
        )
        if not resumable:
            review_path.write_text("", encoding="utf-8")
            processed_path.write_text(
            self._ledger_header(commit, whitelist_signature, self.year), encoding="utf-8"
            )
            records = []
        self.output_directory.mkdir(parents=True, exist_ok=True)

        self.review_directory.joinpath("source.json").write_text(
            json.dumps({"repository": self.repository, "commit": commit}, indent=2) + "\n",
            encoding="utf-8",
        )
        self._process_checkout(
            members,
            processed=processed,
            review_path=review_path,
            processed_path=processed_path,
            output=output,
            records=records,
        )
        return CveRunResult(len(records), len(_profiles_for_records(records)), len(members), output)

    def _process_checkout(
        self,
        members: list[Path],
        *,
        processed: set[str],
        review_path: Path,
        processed_path: Path,
        output: Path,
        records: list[dict[str, Any]],
    ) -> None:
        pending_paths: list[str] = []
        with review_path.open("a", encoding="utf-8", newline="\n") as review:
            for path in members:
                relative = path.relative_to(self.source_directory).as_posix()
                if relative in processed:
                    continue
                records.extend(self._process_one_file(path, review))
                pending_paths.append(relative)
                if len(pending_paths) >= 100:
                    self._write_output(output, records)
                    review.flush()
                    self._append_processed(processed_path, pending_paths)
                    processed.update(pending_paths)
                    pending_paths.clear()
        if pending_paths:
            self._write_output(output, records)
            self._append_processed(processed_path, pending_paths)
            processed.update(pending_paths)
        elif not output.exists():
            self._write_output(output, records)

    def _process_one_file(self, path: Path, review: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        cve = self._read_cve_bytes(path.read_bytes())
        if cve is None:
            return found
        cve_id = str(cve.get("cveMetadata", {}).get("cveId", path.stem))
        match = _CVE_ID.match(cve_id)
        if not match:
            return found
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
            found.append(record)
        return found

    @staticmethod
    def _ledger_header(
        commit: str, whitelist_signature: tuple[int, int], year: int | None
    ) -> str:
        return (
            f"# commit: {commit}\n"
            f"# whitelist-signature: {whitelist_signature[0]}:{whitelist_signature[1]}\n"
            f"# year: {year if year is not None else 'all'}\n"
        )

    @classmethod
    def _read_processed_ledger(
        cls,
        path: Path,
        commit: str,
        whitelist_signature: tuple[int, int],
        year: int | None = None,
    ) -> tuple[set[str], bool]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return set(), False
        expected = cls._ledger_header(commit, whitelist_signature, year).splitlines()
        if lines[:3] != expected:
            return set(), False
        return {line for line in lines[3:] if line and not line.startswith("#")}, True

    @staticmethod
    def _append_processed(path: Path, relative_paths: list[str]) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(f"{relative}\n" for relative in relative_paths))
            handle.flush()

    @staticmethod
    def _write_output(path: Path, records: list[dict[str, Any]]) -> None:
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for record in records:
            unique.setdefault((str(record.get("name", "")), str(record.get("label", ""))), record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(list(unique.values()), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _read_json_array(path: Path, archive: Path | None = None) -> list[dict[str, Any]]:
        if not path.exists():
            archive = archive or path.with_suffix(".zip")
            try:
                with zipfile.ZipFile(archive) as bundle:
                    with bundle.open(path.name) as handle:
                        value = json.load(handle)
            except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
                return []
            return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

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


def _profiles_for_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    people: dict[str, dict[str, Any]] = {}
    for record in records:
        name = record.get("name")
        if not isinstance(name, str):
            continue
        identity = IdentityRegistry.normalize(name)
        people.setdefault(identity, {"name": clean_person_name(name), "biography": "", "contact": []})
    return list(people.values())


def archive_yearly_outputs(
    output_directory: Path,
    archive_directory: Path = Path("data/archives/cve"),
    *,
    current_year: int | None = None,
) -> int:
    """Archive completed historical CVE collections outside temporary output."""

    current_year = current_year or date.today().year
    archive_directory.mkdir(parents=True, exist_ok=True)
    archived = 0
    for source in sorted(Path(output_directory).glob("cve-records-20*.json")):
        match = re.search(r"cve-records-(20\d{2})\.json$", source.name)
        if not match or int(match.group(1)) >= current_year:
            continue
        archive = archive_directory / source.with_suffix(".zip").name
        temporary = archive.with_suffix(".zip.tmp")
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as bundle:
            bundle.write(source, arcname=source.name)
        temporary.replace(archive)
        source.unlink()
        archived += 1
    return archived


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
