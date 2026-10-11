"""Discovery, execution, and lookup primitives for endorsement enrichers."""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .archives import ArchiveStore


class EnrichmentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EnricherContext:
    output_directory: Path = Path("data/enrichments")
    assessors_directory: Path = Path("data/assessors")
    overwrite: bool = True
    playlist_end: int = 0


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    enricher_id: str
    records: int
    output: Path
    status: str


class BaseEnricher:
    """Base class for one independently runnable enrichment dataset."""

    enricher_id = ""

    def run(self, context: EnricherContext) -> EnrichmentResult:
        raise NotImplementedError


def discover_enrichers(directory: Path = Path("enrichers")) -> list[type[BaseEnricher]]:
    directory = directory.resolve()
    if not directory.is_dir():
        raise EnrichmentError(f"Enricher directory does not exist: {directory}")
    found: list[type[BaseEnricher]] = []
    sys.path.insert(0, str(directory.parent))
    try:
        for path in sorted(directory.rglob("*.py")):
            if path.name.startswith("_") or "__pycache__" in path.parts:
                continue
            name = re.sub(r"[^A-Za-z0-9_]", "_", "_".join(path.relative_to(directory).with_suffix("").parts))
            spec = importlib.util.spec_from_file_location(f"_enricher_{name}_{abs(hash(path))}", path)
            if spec is None or spec.loader is None:
                raise EnrichmentError(f"Cannot load enricher module: {path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                raise EnrichmentError(f"Failed to import {path}: {exc}") from exc
            for _, candidate in inspect.getmembers(module, inspect.isclass):
                if candidate is not BaseEnricher and issubclass(candidate, BaseEnricher) and candidate.__module__ == module.__name__:
                    if not isinstance(candidate.enricher_id, str) or not candidate.enricher_id:
                        raise EnrichmentError(f"{path}: enricher_id must be non-empty")
                    found.append(candidate)
    finally:
        sys.path.pop(0)
    ids = [item.enricher_id for item in found]
    if len(ids) != len(set(ids)):
        raise EnrichmentError("Duplicate enricher_id values: " + ", ".join(sorted(set(ids))))
    return sorted(found, key=lambda item: item.enricher_id)


def run_enrichers(classes: list[type[BaseEnricher]], context: EnricherContext, workers: int = 4) -> list[EnrichmentResult]:
    results: list[EnrichmentResult] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(classes) or 1)), thread_name_prefix="enricher") as executor:
        futures = [executor.submit(cls().run, context) for cls in classes]
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda item: item.enricher_id)


class EnrichmentCatalog:
    """Read all JSON datasets and expose normalized evidence-link matches."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self._title_index: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            title = record.get("title")
            if isinstance(title, str):
                for token in set(_normalize_title(title).split()):
                    if len(token) >= 4:
                        self._title_index.setdefault(token, []).append(record)

    @classmethod
    def from_directory(cls, directory: Path = Path("data/enrichments")) -> "EnrichmentCatalog":
        records: list[dict[str, Any]] = []
        for archive_path in sorted(directory.glob("*/data.zip")):
            with zipfile.ZipFile(archive_path) as archive:
                try:
                    document = json.loads(archive.read("data.json"))
                except (KeyError, json.JSONDecodeError) as exc:
                    raise EnrichmentError(f"Invalid enrichment archive: {archive_path}") from exc
            if not isinstance(document, list):
                raise EnrichmentError(f"{archive_path}!data.json must contain an array")
            records.extend(item for item in document if isinstance(item, dict))
        return cls(records)

    def links_for(self, *, assessor_id: str, label: str, subtitle: str | None = None) -> tuple[dict[str, str], ...]:
        target = _normalize_title(label)
        conference = _conference_number(subtitle or "")
        matches: dict[str, dict[str, str]] = {}
        tokens = {token for token in target.split() if len(token) >= 4}
        candidates: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for token in tokens:
            for record in self._title_index.get(token, ()):
                if id(record) not in seen_ids:
                    seen_ids.add(id(record))
                    candidates.append(record)
        for record in candidates:
            if record.get("assessor-id") not in (None, assessor_id):
                continue
            title = record.get("title")
            url = record.get("url") or record.get("webpage_url")
            if not isinstance(title, str) or not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            candidate = _normalize_title(title)
            talk_candidate = _candidate_talk_title(title)
            if not _titles_match(target, candidate, talk_candidate):
                continue
            if conference and record.get("conference") and str(record["conference"]) != conference:
                continue
            matches[url] = {"title": title.strip(), "url": url}
        return tuple(matches[key] for key in sorted(matches))


def write_json_zip(path: Path, records: list[dict[str, Any]], *, overwrite: bool = True) -> EnrichmentResult:
    existed = path.exists()
    if path.exists() and not overwrite:
        return EnrichmentResult(path.parent.name, len(records), path, "skipped")
    path.parent.mkdir(parents=True, exist_ok=True)
    store = ArchiveStore(path)
    store.write("data.json", (json.dumps(records, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return EnrichmentResult(path.parent.name, len(records), path, "overwritten" if existed else "created")


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _candidate_talk_title(value: str) -> str:
    """Remove the channel's conference and speaker prefix from a video title."""

    parts = [part.strip() for part in value.split(" - ") if part.strip()]
    return _normalize_title(parts[-1]) if len(parts) > 1 else _normalize_title(value)


def _titles_match(target: str, candidate: str, talk_candidate: str) -> bool:
    if not target or not candidate:
        return False
    if target == candidate or target in candidate or candidate in target:
        return True
    target_tokens = _title_tokens(target)
    candidate_tokens = _title_tokens(talk_candidate)
    overlap = target_tokens & candidate_tokens
    if len(overlap) >= 3 and len(overlap) / max(1, min(len(target_tokens), len(candidate_tokens))) >= 0.6:
        return True
    return len(overlap) >= 4 and SequenceMatcher(None, target, talk_candidate).ratio() >= 0.55


def _title_tokens(value: str) -> set[str]:
    stopwords = {"a", "an", "and", "for", "of", "the", "to", "in", "on", "with"}
    return {token for token in value.split() if len(token) >= 3 and token not in stopwords}


def _conference_number(value: str) -> str | None:
    match = re.search(r"(?:def\s*con|defcon)[^0-9]{0,4}(\d{1,2})", value.casefold())
    return match.group(1) if match else None
