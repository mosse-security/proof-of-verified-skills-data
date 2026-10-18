from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import is_non_endorsement_session, validate_endorsement_record
from .domains import ALLOWED_DOMAINS
from .identity_registry import IdentityRegistry, clean_person_name


@dataclass(frozen=True, slots=True)
class IndividualMergeResult:
    people: int
    endorsements: int
    created: int
    overwritten: int
    skipped: int
    files: tuple[Path, ...]


class IndividualMergeError(ValueError):
    pass


def build_assessor_individuals(
    assessor_id: str,
    *,
    endorsements_directory: Path = Path("tmp/endorsements"),
    profiles_directory: Path = Path("tmp/profiles"),
    assessors_directory: Path = Path("data/assessors"),
) -> int:
    """Rebuild one assessor's approved individual snapshot from its scrape."""

    registry = IdentityRegistry.for_assessor(
        assessor_id, data_directory=assessors_directory.parent
    )
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    source_directory = endorsements_directory / assessor_id
    for source_path in sorted(source_directory.rglob("*.json")) if source_directory.exists() else []:
        document = json.loads(source_path.read_text(encoding="utf-8"))
        records = document if isinstance(document, list) else [document]
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise IndividualMergeError(f"{source_path}[{index}] must be a JSON object")
            validate_endorsement_record(record, source=f"{source_path}[{index}]")
            name = _clean_name(record["name"])
            if not registry.allows(name) or _looks_like_talk_title(name, record.get("label", "")):
                continue
            record = dict(record)
            record["name"] = name
            identity = _person_identity(name)
            person = grouped.setdefault(identity, {"name": name, "records": {}, "profiles": []})
            key = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            person["records"].setdefault(key, record)

    profile_directory = profiles_directory / assessor_id
    for profile_path in sorted(profile_directory.rglob("*.json")) if profile_directory.exists() else []:
        document = json.loads(profile_path.read_text(encoding="utf-8"))
        profiles = document if isinstance(document, list) else [document]
        for index, profile in enumerate(profiles):
            _validate_profile(profile, source=f"{profile_path}[{index}]")
            name = _clean_name(profile["name"])
            if not registry.allows(name):
                continue
            person = grouped.setdefault(
                _person_identity(name), {"name": name, "records": {}, "profiles": []}
            )
            person["profiles"].append(profile)

    output = assessors_directory / assessor_id / "individuals"
    previous = _existing_individuals(output)
    cleanup_generated_directory(output)
    output.mkdir(parents=True, exist_ok=True)
    used: dict[str, str] = {}
    for identity, person in sorted(grouped.items()):
        records = sorted(person["records"].values(), key=_endorsement_sort_key)
        if not records:
            continue
        payload = {
            "name": person["name"],
            "last-updated": "",
            "biography": "",
            "contact": _merged_contacts(person["profiles"]),
            "stats": _individual_stats(records),
            "endorsements": records,
        }
        payload["last-updated"] = _preserved_timestamp(previous.get(identity), payload)
        _validate_individual(payload, source=str(output))
        path = output / _individual_filename(person["name"], identity, used)
        _atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return len([p for p in output.glob("*.json")])


def merge_canonical_individuals(
    *,
    assessors_directory: Path = Path("data/assessors"),
    output_directory: Path = Path("data/individuals"),
) -> int:
    """Delete and rebuild canonical individuals solely from assessor-local files."""

    previous = _existing_individuals(output_directory)
    # This is deliberately a clean rebuild.  No canonical file may survive
    # after its assessor-local source has disappeared or been rejected.
    cleanup_generated_directory(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    if not assessors_directory.exists():
        return 0
    aggregate: dict[str, dict[str, Any]] = {}
    for assessor_dir in sorted(p for p in assessors_directory.iterdir() if p.is_dir()):
        individual_directory = assessor_dir / "individuals"
        if not individual_directory.is_dir():
            continue
        for path in sorted(individual_directory.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            _validate_individual(document, source=str(path))
            identity = _person_identity(document["name"])
            person = aggregate.setdefault(identity, {"name": document["name"], "records": []})
            person["records"].extend(document["endorsements"])
    used: dict[str, str] = {}
    for identity, person in sorted(aggregate.items()):
        records = sorted(person["records"], key=_endorsement_sort_key)
        payload = {
            "name": person["name"],
            "last-updated": "",
            "biography": "",
            "contact": [],
            "stats": _individual_stats(records),
            "endorsements": records,
        }
        payload["last-updated"] = _preserved_timestamp(previous.get(identity), payload)
        _validate_individual(payload, source=str(output_directory))
        path = output_directory / _individual_filename(person["name"], identity, used)
        _atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return len(aggregate)


def apply_enrichments_to_assessor_individuals(
    assessor_ids: set[str] | None = None,
    *,
    assessors_directory: Path = Path("data/assessors"),
    enrichments_directory: Path = Path("data/enrichments"),
) -> int:
    """Apply enrichment evidence links directly to assessor-local profiles."""

    from .enrichment import EnrichmentCatalog

    catalog = EnrichmentCatalog.from_directory(enrichments_directory)
    updated = 0
    for assessor_dir in sorted(p for p in assessors_directory.iterdir() if p.is_dir()):
        assessor_id = assessor_dir.name
        if assessor_ids is not None and assessor_id not in assessor_ids:
            continue
        for path in sorted((assessor_dir / "individuals").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for record in document.get("endorsements", []):
                links = catalog.links_for(
                    assessor_id=assessor_id,
                    label=str(record.get("label", "")),
                    subtitle=str(record.get("subtitle", "")),
                )
                existing = {str(item.get("url")): item for item in record.get("evidence-links", [])}
                for link in links:
                    existing[link["url"]] = link
                merged = [existing[key] for key in sorted(existing)]
                if merged != record.get("evidence-links", []):
                    record["evidence-links"] = merged
                    record["evidence"] = bool(merged)
                    changed = True
            if changed:
                document["stats"] = _individual_stats(document["endorsements"])
                document["last-updated"] = _utc_timestamp()
                _validate_individual(document, source=str(path))
                _atomic_write(path, (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                updated += 1
    return updated


def cleanup_generated_directory(directory: Path) -> int:
    """Remove generated files below one temporary output directory."""

    if not directory.exists():
        return 0
    removed = 0
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


def merge_endorsements(
    endorsements_directory: Path = Path("tmp/endorsements"),
    output_directory: Path = Path("data/individuals"),
    *,
    overwrite: bool = True,
    profiles_directory: Path = Path("tmp/profiles"),
    allow_empty_output: bool = False,
    identity_registry: IdentityRegistry | None = None,
    assessors_directory: Path | None = None,
) -> IndividualMergeResult:
    """Merge all endorsement records into one template-shaped file per person."""

    assessor_root = assessors_directory or (
        Path("data/assessors")
        if output_directory == Path("data/individuals")
        else output_directory.parent / "assessors"
    )
    previous_output = _existing_individuals(output_directory)
    # This is a snapshot rebuild. Clear assessor-local output before reading
    # or writing anything so failed and empty runs cannot leave old records.
    _clear_assessor_individual_outputs(assessor_root)

    registry = identity_registry
    enforce_registry = (
        registry is not None
        or assessors_directory is not None
        or output_directory == Path("data/individuals")
    )
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    source_files = sorted(endorsements_directory.rglob("*.json"))
    for source_path in source_files:
        try:
            document = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndividualMergeError(f"Cannot read {source_path}: {exc}") from exc
        records = document if isinstance(document, list) else [document]
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise IndividualMergeError(f"{source_path}[{index}] must be a JSON object")
            try:
                validate_endorsement_record(record, source=f"{source_path}[{index}]")
            except ValueError as exc:
                raise IndividualMergeError(str(exc)) from exc
            name = _clean_name(record["name"])
            if not name:
                raise IndividualMergeError(f"{source_path}[{index}].name is empty")
            record["name"] = name
            record_registry = (
                registry
                or IdentityRegistry.for_assessor(str(record.get("assessor-id", "unknown")))
                if enforce_registry
                else None
            )
            if record_registry is not None and not record_registry.allows(name):
                continue
            if _looks_like_talk_title(name, record.get("label", "")):
                # A malformed scraper row must not become a persisted person.
                # Keep the source row available for debugging, but exclude it
                # from the individual dataset until its parser is corrected.
                continue
            identity = _person_identity(name)
            person = grouped.setdefault(identity, {"name": name, "records": {}})
            # Keep the first spelling, but make endorsement duplication idempotent.
            key = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            person["records"].setdefault(key, record)

    for profile_path in sorted(profiles_directory.rglob("*.json")):
        try:
            document = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndividualMergeError(f"Cannot read {profile_path}: {exc}") from exc
        profiles = document if isinstance(document, list) else [document]
        for index, profile in enumerate(profiles):
            _validate_profile(profile, source=f"{profile_path}[{index}]")
            name = _clean_name(profile["name"])
            profile_registry = (
                registry or IdentityRegistry.for_assessor(profile_path.parent.name)
                if enforce_registry
                else None
            )
            if profile_registry is not None and not profile_registry.allows(name):
                continue
            identity = _person_identity(name)
            person = grouped.setdefault(identity, {"name": name, "records": {}})
            person.setdefault("profiles", []).append(profile)

    output_directory.mkdir(parents=True, exist_ok=True)
    for existing_path in output_directory.glob("*.json"):
        existing_path.unlink(missing_ok=True)
    used_paths: dict[str, str] = {}
    files: list[Path] = []
    created = overwritten = skipped = 0
    total = 0
    for identity, person in sorted(grouped.items(), key=lambda item: item[0]):
        records = sorted(person["records"].values(), key=_endorsement_sort_key)
        total += len(records)
        filename = _individual_filename(person["name"], identity, used_paths)
        path = output_directory / filename
        # A profile-only pass must never erase an existing person's
        # endorsements. This also makes cleanup/rerun races harmless.
        if not records and path.exists():
            if overwrite:
                _upgrade_existing_timestamp(path)
            skipped += 1
            files.append(path)
            continue
        payload = {
            "name": person["name"],
            "last-updated": "",
            "biography": "",
            "contact": _merged_contacts(person.get("profiles", [])),
            "stats": _individual_stats(records),
            "endorsements": records,
        }
        payload["last-updated"] = _preserved_timestamp(
            previous_output.get(identity), payload
        )
        _validate_individual(payload, source=str(path))
        if path.exists() and not overwrite:
            skipped += 1
        else:
            existed = path.exists()
            if existed:
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    existing = None
                if existing == payload:
                    skipped += 1
                    files.append(path)
                    continue
            _atomic_write(
                path,
                (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
            overwritten += int(existed)
            created += int(not existed)
        files.append(path)

    _rebuild_assessor_outputs(
        output_directory,
        assessor_root=assessor_root,
        identity_registry=registry,
    )

    return IndividualMergeResult(
        people=len(grouped),
        endorsements=total,
        created=created,
        overwritten=overwritten,
        skipped=skipped,
        files=tuple(files),
    )


def _validate_individual(document: dict[str, Any], *, source: str) -> None:
    expected = {"name", "last-updated", "biography", "contact", "stats", "endorsements"}
    if set(document) != expected:
        raise IndividualMergeError(f"{source} must contain exactly {sorted(expected)}")
    if not isinstance(document["name"], str) or not document["name"].strip():
        raise IndividualMergeError(f"{source}.name must be a non-empty string")
    if not _is_timestamp(document["last-updated"]):
        raise IndividualMergeError(
            f"{source}.last-updated must be an ISO-8601 UTC timestamp"
        )
    if not isinstance(document["biography"], str):
        raise IndividualMergeError(f"{source}.biography must be a string")
    if not isinstance(document["contact"], list):
        raise IndividualMergeError(f"{source}.contact must be an array")
    if not isinstance(document["endorsements"], list):
        raise IndividualMergeError(f"{source}.endorsements must be an array")
    for index, endorsement in enumerate(document["endorsements"]):
        validate_endorsement_record(endorsement, source=f"{source}.endorsements[{index}]")
    if document["stats"] != _individual_stats(document["endorsements"]):
        raise IndividualMergeError(f"{source}.stats does not match endorsements")


def _individual_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_domain = {domain: 0 for domain in ALLOWED_DOMAINS}
    with_evidence = 0
    assessors: set[str] = set()
    for record in records:
        assessor_id = record.get("assessor-id")
        if isinstance(assessor_id, str) and assessor_id:
            assessors.add(assessor_id)
        if record.get("evidence") is True:
            with_evidence += 1
        for domain in record["domains"]:
            by_domain[domain] += 1
    return {
        "endorsements": len(records),
        "assessors": len(assessors),
        "with-evidence": with_evidence,
        "without-evidence": len(records) - with_evidence,
        "by-domain": by_domain,
    }


def _last_updated_for(path: Path, payload: dict[str, Any]) -> str:
    """Preserve the timestamp when content is unchanged; otherwise refresh it."""

    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict):
            previous_content = dict(existing)
            previous_timestamp = previous_content.pop("last-updated", None)
            current_content = dict(payload)
            current_content.pop("last-updated", None)
            if previous_content == current_content and _is_timestamp(previous_timestamp):
                return previous_timestamp
    return _utc_timestamp()


def _existing_individuals(directory: Path) -> dict[str, dict[str, Any]]:
    """Snapshot generated individuals before a clean rebuild removes them."""

    result: dict[str, dict[str, Any]] = {}
    if not directory.is_dir():
        return result
    for path in directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(document, dict) and isinstance(document.get("name"), str):
            result[_person_identity(document["name"])] = document
    return result


def _preserved_timestamp(
    previous: dict[str, Any] | None, payload: dict[str, Any]
) -> str:
    """Keep the prior timestamp only when every other field is deeply equal."""

    if isinstance(previous, dict):
        previous_content = dict(previous)
        previous_timestamp = previous_content.pop("last-updated", None)
        current_content = dict(payload)
        current_content.pop("last-updated", None)
        if previous_content == current_content and _is_timestamp(previous_timestamp):
            return previous_timestamp
    return _utc_timestamp()


def _upgrade_existing_timestamp(path: Path) -> None:
    """Add the timestamp to legacy individual records without source rows."""

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(existing, dict):
        return
    changed = False
    if "last-updated" not in existing:
        existing["last-updated"] = _utc_timestamp()
        changed = True
    expected_stats = _individual_stats(existing.get("endorsements", []))
    if existing.get("stats") != expected_stats:
        existing["stats"] = expected_stats
        changed = True
    if not changed:
        return
    _validate_individual(existing, source=str(path))
    _atomic_write(
        path,
        (json.dumps(existing, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def _rebuild_assessor_outputs(
    output_directory: Path,
    *,
    assessor_root: Path,
    identity_registry: IdentityRegistry | None = None,
) -> None:
    """Write assessor-local profiles, then rebuild the canonical individuals set."""
    assessor_root.mkdir(parents=True, exist_ok=True)
    previous_by_assessor = {
        assessor_dir.name: _existing_individuals(assessor_dir / "individuals")
        for assessor_dir in assessor_root.iterdir()
        if assessor_dir.is_dir()
    }
    _clear_assessor_individual_outputs(assessor_root)
    by_assessor: dict[str, dict[str, dict[str, Any]]] = {}
    current_documents: list[dict[str, Any]] = []
    for path in output_directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(document, dict) and document.get("endorsements"):
            current_documents.append(document)

    for document in current_documents:
        name = str(document["name"])
        for record in document["endorsements"]:
            assessor_id = str(record.get("assessor-id", "unknown"))
            registry = identity_registry or IdentityRegistry.for_assessor(assessor_id)
            if not registry.allows(name):
                continue
            person_id = _person_identity(name)
            assessor_people = by_assessor.setdefault(assessor_id, {})
            person = assessor_people.setdefault(person_id, {"name": name, "records": []})
            person["records"].append(record)

    for assessor_id, people in by_assessor.items():
        individual_dir = assessor_root / assessor_id / "individuals"
        individual_dir.mkdir(parents=True, exist_ok=True)
        used: dict[str, str] = {}
        for person_id, person in sorted(people.items()):
            payload = {
                "name": person["name"],
                "last-updated": "",
                "biography": "",
                "contact": [],
                "stats": _individual_stats(person["records"]),
                "endorsements": sorted(person["records"], key=_endorsement_sort_key),
            }
            payload["last-updated"] = _preserved_timestamp(
                previous_by_assessor.get(assessor_id, {}).get(person_id), payload
            )
            _validate_individual(payload, source=str(individual_dir))
            path = individual_dir / _individual_filename(person["name"], person_id, used)
            _atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    aggregate: dict[str, dict[str, Any]] = {}
    for assessor_dir in assessor_root.iterdir():
        individual_dir = assessor_dir / "individuals"
        if not individual_dir.is_dir():
            continue
        for path in individual_dir.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            identity = _person_identity(str(document["name"]))
            person = aggregate.setdefault(identity, {"name": document["name"], "records": []})
            person["records"].extend(document.get("endorsements", []))

    previous_canonical = _existing_individuals(output_directory)
    for path in output_directory.glob("*.json"):
        path.unlink(missing_ok=True)
    used: dict[str, str] = {}
    for identity, person in sorted(aggregate.items()):
        records = sorted(person["records"], key=_endorsement_sort_key)
        payload = {
            "name": person["name"],
            "last-updated": "",
            "biography": "",
            "contact": [],
            "stats": _individual_stats(records),
            "endorsements": records,
        }
        payload["last-updated"] = _preserved_timestamp(
            previous_canonical.get(identity), payload
        )
        _validate_individual(payload, source=str(output_directory))
        path = output_directory / _individual_filename(person["name"], identity, used)
        _atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _clear_assessor_individual_outputs(assessor_root: Path) -> int:
    """Delete every generated JSON below every assessor's individuals folder."""

    removed = 0
    if not assessor_root.exists():
        return removed
    for assessor_dir in assessor_root.iterdir():
        individual_dir = assessor_dir / "individuals"
        if not individual_dir.is_dir():
            continue
        for path in sorted(individual_dir.rglob("*.json")):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
                removed += 1
        for directory in sorted(
            (p for p in individual_dir.rglob("*") if p.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
    return removed


def _remove_stale_non_endorsement_sessions(output_directory: Path) -> int:
    """Purge event sessions left by older runs from final individual files."""

    removed = 0
    for path in output_directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict) or not isinstance(document.get("endorsements"), list):
            continue
        records = document["endorsements"]
        kept = [
            record
            for record in records
            if not (
                isinstance(record, dict)
                and record.get("domains") == ["unknown"]
                and is_non_endorsement_session(
                    str(record.get("label", "")),
                    str(record.get("description", "")),
                    str(record.get("subtitle", "")),
                )
            )
        ]
        if len(kept) == len(records):
            continue
        removed += len(records) - len(kept)
        if not kept:
            path.unlink(missing_ok=True)
            continue
        document["endorsements"] = kept
        document["stats"] = _individual_stats(kept)
        document["last-updated"] = _utc_timestamp()
        _validate_individual(document, source=str(path))
        _atomic_write(path, (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return removed


def _remove_unapproved_existing_profiles(
    output_directory: Path,
    *,
    identity_registry: IdentityRegistry | None = None,
) -> int:
    """Remove profiles whose source endorsements are no longer approved.

    This handles the case where a reviewer moves a name out of a whitelist
    after a previous merge. Existing JSON must not survive that decision.
    """
    registries: dict[str, IdentityRegistry] = {}
    removed = 0
    for path in output_directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        records = document.get("endorsements")
        if not isinstance(records, list):
            continue
        if not records:
            path.unlink(missing_ok=True)
            removed += 1
            continue
        document_name = document.get("name")
        if not isinstance(document_name, str) or not document_name.strip():
            path.unlink(missing_ok=True)
            removed += 1
            continue
        approved = False
        for record in records:
            if not isinstance(record, dict):
                continue
            assessor_id = str(record.get("assessor-id", "unknown"))
            registry = identity_registry or registries.setdefault(
                assessor_id, IdentityRegistry.for_assessor(assessor_id)
            )
            if registry.allows(document_name):
                approved = True
                break
        if not approved:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _is_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _validate_profile(profile: Any, *, source: str) -> None:
    if not isinstance(profile, dict) or set(profile) != {"name", "biography", "contact"}:
        raise IndividualMergeError(
            f"{source} must contain exactly name, biography, and contact"
        )
    if not isinstance(profile["name"], str) or not profile["name"].strip():
        raise IndividualMergeError(f"{source}.name must be a non-empty string")
    if not isinstance(profile["biography"], str):
        raise IndividualMergeError(f"{source}.biography must be a string")
    if not isinstance(profile["contact"], list):
        raise IndividualMergeError(f"{source}.contact must be an array")
    for index, contact in enumerate(profile["contact"]):
        if not isinstance(contact, dict) or not isinstance(contact.get("label"), str):
            raise IndividualMergeError(f"{source}.contact[{index}] is invalid")
        if set(contact) - {"label", "url", "email"}:
            raise IndividualMergeError(f"{source}.contact[{index}] has unsupported fields")


def _merged_contacts(profiles: list[dict[str, Any]]) -> list[dict[str, str]]:
    contacts: dict[str, dict[str, str]] = {}
    for profile in profiles:
        for contact in profile["contact"]:
            key = json.dumps(contact, ensure_ascii=False, sort_keys=True)
            contacts.setdefault(key, contact)
    return [contacts[key] for key in sorted(contacts)]


def _clean_name(value: str) -> str:
    return clean_person_name(value)


def _looks_like_talk_title(name: str, label: str = "") -> bool:
    value = " ".join(name.casefold().split())
    label_shape = " ".join(str(label).split())
    label_value = label_shape.casefold()
    if value and value == label_value:
        return True
    # Schedule titles beginning with an article are especially easy to retain
    # as people when an older parser emitted the row in reverse order.  Keep
    # initials such as ``A. Smith`` valid by requiring a word after the
    # article, and only apply this when the other side has a person shape.
    if label_value and value.startswith(("a ", "an ", "the ")):
        if _looks_like_person_shape(label_shape):
            return True
    if len(value.split()) > 6 or any(char in value for char in ":;!?\n"):
        return True
    markers = (
        "a decade of ", "and knowledge in ", "attack analysis", "building an ",
        "circuit security ", "creating a powerful ", "cyber fast track;",
        "everything they told me", "getting the most out of ", "ghost in the wires:",
        "hack your way into ", "hackers saving the world", "how to ",
        "introducing the ", "introduction to ", "love the smart meter",
        "more new shiny ", "my password cracking ", "network security ",
        "originally presented ", "patching the human ", "pen testing ",
        "penetration testing ", "personal darknet ", "political activism ",
        "privilege escalation ", "pwned in ", "rescuing the ", "running a successful ",
        "securing the internet", "simple security ", "so you got yourself ",
        "social zombies:", "taking cookie hijacking", "tales from the ",
        "the art", "the badmin project", "the evolution of ", "the future of ",
        "the glitch:", "the patsy proxy:", "the red team ", "things being a new ",
        "vulnerability spider", "web app testing ", "what locksport ",
        "you can't buy security",
        "longtail ", "introduction ", "such keynote ", "enterprise security",
        "the physical world", "university education in security", "the m",
        "5min ", "a brief history of ", "a developer", "a guided tour", "a n00bie",
        "a survey of ", "analysis for ", "an anti-forensics", "an encyclpwnia",
        "applying the ", "attack paths:", "attacking ", "bridging the gap",
        "building a ", "building better ", "cognitive injection:", "crypto ",
        "dynamic analysis", "everything you ever", "exploiting ", "finding the ",
        "getting schoole", "hacking ", "hardening ", "hello asm", "how building ",
        "identifying evil", "information security", "intercepting ", "intrusion hunting",
        "kinetic pwnage", "learning mainframe", "malfunction's functions", "malware ",
        "mobile application", "modern embedded", "new shiny", "on defending ",
        "open source threat", "operating in the shadows", "panel", "passing the torch",
        "patching windows", "phishing like", "physical security", "practical exploitation",
        "privacy in a ", "proactive application", "protocol me", "red teaming",
        "sandboxes from", "security hopscotch", "security training", "shattering the",
        "shooting phish", "simple network", "smarter defending", "so hopelessly",
        "soft skills", "spy vs", "stacking the", "stagefright", "state of the",
        "steal all", "stretching the", "sys admin", "taking the bdsm", "the canary",
        "the cavalry", "the high risk", "the human", "the internet", "the law of",
        "the little-known", "the malware", "the message", "the messenger", "the netsniff",
        "the pentesters", "the phony", "the problems", "third party", "tizen security",
        "vulnerability assessment", "welcome to the family", "what if ", "what to expect",
        "when a powerful", "windows attacks", "you're in the",
    )
    if any(value.startswith(marker) for marker in markers):
        return True
    # A number of historical schedules use a single product/tool/session
    # word as the title (for example ``Ansible``).  A one-word value paired
    # with a multi-word person-shaped label is therefore suspicious, while
    # ordinary aliases remain accepted when there is no such context.
    if (
        label_value
        and len(value.split()) == 1
        and len(label_value.split()) >= 2
        and _looks_like_person_shape(label_shape)
        and value.casefold() in {"ansible", "frame", "attacks", "defense", "development"}
    ):
        return True
    # Reversed schedule rows often have a person-looking label and a title-
    # looking name. This catches orientation bugs without rejecting ordinary
    # pseudonyms such as "The Grugq".
    return bool(label_value and _looks_like_person_shape(label_shape) and not _looks_like_person_shape(name))


def _looks_like_person_shape(value: str) -> bool:
    words = value.split()
    if not (1 <= len(words) <= 6) or len(value) > 80:
        return False
    if any(char in value for char in ":;!?\n"):
        return False
    return any(char.isupper() for char in value) and not value.startswith((
        "a ", "an ", "the ", "how ", "what ", "why ", "building ", "attack",
        "analysis ", "security ", "introduction ", "information security", "panel",
        "network ", "malware ", "hacking ", "exploiting ", "privacy ", "vulnerability",
    ))


def _person_identity(name: str) -> str:
    """Return a stable identity key across cosmetic name variants.

    Accents, punctuation, hyphens, and spacing are presentation differences
    for identity grouping.  Keeping them in the key created duplicate people
    and filename suffixes such as ``--074c477062`` for one individual.
    """

    normalized = unicodedata.normalize("NFKD", name).casefold()
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return "".join(char for char in normalized if char.isalnum())


def _endorsement_sort_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["year"],
        record.get("assessor-id", ""),
        record.get("type", ""),
        record.get("label", "").casefold(),
        record.get("url", ""),
    )


def _individual_filename(
    name: str, identity: str, used_paths: dict[str, str]
) -> str:
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower() or "individual"
    filename = f"{slug}.json"
    previous = used_paths.get(filename)
    if previous is not None and previous != identity:
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
        filename = f"{slug}--{digest}.json"
    used_paths[filename] = identity
    return filename


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="merge-individuals",
        description="Merge endorsement records into one file per individual.",
    )
    parser.add_argument(
        "--assessors-dir", type=Path, default=Path("data/assessors"),
        help="Directory containing assessor-local individual snapshots.",
    )
    parser.add_argument(
        "--endorsements-dir", type=Path, default=Path("tmp/endorsements")
    )
    parser.add_argument(
        "--profiles-dir", type=Path, default=Path("tmp/profiles")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/individuals")
    )
    parser.add_argument(
        "--allow-empty-output",
        action="store_true",
        help="Allow rebuilding into an existing empty output directory (timestamps cannot be preserved).",
    )
    parser.add_argument(
        "--keep-tmp",
        action="store_true",
        help="Keep temporary endorsements and profiles after merging.",
    )
    overwrite = parser.add_mutually_exclusive_group()
    overwrite.add_argument(
        "--overwrite",
        dest="overwrite",
        action="store_true",
        help="Replace existing individual files (the default).",
    )
    overwrite.add_argument(
        "--no-overwrite",
        dest="overwrite",
        action="store_false",
        help="Preserve existing individual files.",
    )
    parser.set_defaults(overwrite=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        people = merge_canonical_individuals(
            assessors_directory=args.assessors_dir,
            output_directory=args.output_dir,
        )
    except (OSError, IndividualMergeError) as exc:
        print(f"Individual merge failed: {exc}")
        return 1
    print(
        f"Canonical individuals: people={people} output={args.output_dir}"
    )
    return 0


def _cleanup_tmp(args: argparse.Namespace) -> int:
    removed = cleanup_generated_directory(args.endorsements_dir)
    removed += cleanup_generated_directory(args.profiles_dir)
    return removed


if __name__ == "__main__":
    raise SystemExit(main())



