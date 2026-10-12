from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .domains import detect_domains, detect_subspecialties, normalize_domains, normalize_subspecialties, validate_record_domains


REQUIRED_ENDORSEMENT_FIELDS = (
    "name",
    "label",
    "description",
    "type",
    "assessor",
    "assessor-id",
    "assessor-category",
    "assessor-rigor-level",
    "reviewType",
    "url",
    "evidence-links",
    "evidence",
    "year",
    "domains",
)
OPTIONAL_ENDORSEMENT_FIELDS = ("subtitle", "subspecialties")
ENDORSEMENT_FIELDS = (*REQUIRED_ENDORSEMENT_FIELDS, *OPTIONAL_ENDORSEMENT_FIELDS)


class EndorsementSchemaError(ValueError):
    pass


_NON_ENDORSEMENT_SESSION_RE = re.compile(
    r"\bpanel\b|\bkeynote\b|locknote|comedy|awards?|ceremon(?:y|ies)|"
    r"movie night|closing|DEF CON 101|DC101|meet (?:the )?(?:feds|EFF)|"
    r"hackerspaces?|career|entrepreneur|startup|diversity|community",
    re.IGNORECASE,
)


def is_non_endorsement_session(
    label: str, description: str = "", subtitle: str = ""
) -> bool:
    """Identify clearly non-endorsement event sessions.

    We only exclude sessions with enough source text to classify them as an
    event. A short or missing abstract remains in the dataset as ``unknown``
    rather than being silently discarded by this filter.
    """

    text = " ".join(value for value in (label, description, subtitle) if value)
    if len(text.strip()) < 100 or re.search(
        r"no abstract|abstract coming soon", text, re.IGNORECASE
    ):
        return False
    return bool(_NON_ENDORSEMENT_SESSION_RE.search(text))


def validate_profile_record(record: Mapping[str, Any], *, source: str = "profile") -> None:
    if set(record) != {"name", "biography", "contact"}:
        raise EndorsementSchemaError(
            f"{source} must contain exactly name, biography, and contact"
        )
    if not isinstance(record["name"], str) or not record["name"].strip():
        raise EndorsementSchemaError(f"{source}.name must be a non-empty string")
    if not isinstance(record["biography"], str):
        raise EndorsementSchemaError(f"{source}.biography must be a string")
    if not isinstance(record["contact"], list):
        raise EndorsementSchemaError(f"{source}.contact must be an array")
    for index, contact in enumerate(record["contact"]):
        if not isinstance(contact, dict) or not isinstance(contact.get("label"), str):
            raise EndorsementSchemaError(f"{source}.contact[{index}] is invalid")
        if set(contact) - {"label", "url", "email"}:
            raise EndorsementSchemaError(
                f"{source}.contact[{index}] has unsupported fields"
            )


@dataclass(frozen=True, slots=True)
class AssessorMetadata:
    """Assessor fields copied into every endorsement template record."""

    id: str
    name: str
    category: str
    rigor_level: str
    review_type: str

    @classmethod
    def from_file(cls, path: Path) -> AssessorMetadata:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EndorsementSchemaError(
                f"Cannot read assessor metadata from {path}: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise EndorsementSchemaError(f"{path} must contain a JSON object")

        peer_review = document.get("peerReview")
        values = {
            "id": document.get("id"),
            "name": document.get("name"),
            "category": document.get("category"),
            "rigor_level": (
                peer_review.get("rigorLevel")
                if isinstance(peer_review, dict)
                else None
            ),
            "review_type": (
                peer_review.get("reviewType")
                if isinstance(peer_review, dict)
                else None
            ),
        }
        invalid = [
            label
            for label, value in values.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if invalid:
            raise EndorsementSchemaError(
                f"{path} is missing non-empty assessor field(s): "
                + ", ".join(invalid)
            )
        metadata = cls(**values)
        if path.stem != metadata.id:
            raise EndorsementSchemaError(
                f"Assessor file {path.name!r} contains id {metadata.id!r}"
            )
        return metadata


def build_endorsement_record(
    *,
    name: str,
    label: str,
    description: str,
    endorsement_type: str,
    assessor: AssessorMetadata,
    url: str,
    year: int,
    domains: Iterable[str],
    evidence_links: Iterable[Mapping[str, str]] = (),
    subspecialties: Mapping[str, Iterable[str]] | None = None,
    subtitle: str | None = None,
) -> dict[str, Any]:
    """Build and validate one record matching data/templates/endorsement.tpl."""

    normalized_evidence_links = [dict(link) for link in evidence_links]
    record: dict[str, Any] = {
        "name": name,
        "label": label,
        "description": description,
        "type": endorsement_type,
        "assessor": assessor.name,
        "assessor-id": assessor.id,
        "assessor-category": assessor.category,
        "assessor-rigor-level": assessor.rigor_level,
        "reviewType": assessor.review_type,
    }
    if subtitle is not None:
        record["subtitle"] = subtitle
    domain_values = tuple(domains)
    detected_domains = normalize_domains(domain_values)
    if not domain_values or detected_domains == ("unknown",):
        detected_domains = detect_domains(name, label, description, subtitle)
    specialty_values = subspecialties
    if specialty_values is None:
        specialty_values = detect_subspecialties(name, label, description, subtitle, domains=detected_domains)
    record.update(
        {
            "url": url,
            "evidence-links": normalized_evidence_links,
            "evidence": bool(normalized_evidence_links),
            "year": year,
            "domains": list(detected_domains),
            "subspecialties": {domain: list(names) for domain, names in normalize_subspecialties(specialty_values, domains=detected_domains).items()},
        }
    )
    validate_endorsement_record(record, assessor=assessor)
    return record


def validate_endorsement_record(
    record: Mapping[str, Any],
    *,
    source: str = "record",
    assessor: AssessorMetadata | None = None,
) -> None:
    """Enforce the endorsement template, including its optional subtitle."""

    missing = [field for field in REQUIRED_ENDORSEMENT_FIELDS if field not in record]
    if missing:
        raise EndorsementSchemaError(
            f"{source} is missing required endorsement field(s): " + ", ".join(missing)
        )
    unexpected = sorted(set(record) - set(ENDORSEMENT_FIELDS))
    if unexpected:
        raise EndorsementSchemaError(
            f"{source} has unsupported endorsement field(s): " + ", ".join(unexpected)
        )

    text_fields = (
        "name",
        "label",
        "description",
        "type",
        "assessor",
        "assessor-id",
        "assessor-category",
        "assessor-rigor-level",
        "reviewType",
        "url",
    )
    for field in text_fields:
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise EndorsementSchemaError(f"{source}.{field} must be a non-empty string")
    if "subtitle" in record:
        subtitle = record["subtitle"]
        if not isinstance(subtitle, str) or not subtitle.strip():
            raise EndorsementSchemaError(
                f"{source}.subtitle must be a non-empty string when present"
            )

    year = record["year"]
    if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
        raise EndorsementSchemaError(
            f"{source}.year must be a four-digit integer"
        )
    parsed_url = urlsplit(record["url"])
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise EndorsementSchemaError(f"{source}.url must be an absolute HTTP(S) URL")

    links = record["evidence-links"]
    if not isinstance(links, list):
        raise EndorsementSchemaError(f"{source}.evidence-links must be an array")
    for index, link in enumerate(links):
        if not isinstance(link, dict) or set(link) != {"title", "url"}:
            raise EndorsementSchemaError(
                f"{source}.evidence-links[{index}] must contain title and url"
            )
        if not isinstance(link["title"], str) or not link["title"].strip():
            raise EndorsementSchemaError(
                f"{source}.evidence-links[{index}].title must be non-empty"
            )
        if not isinstance(link["url"], str) or not link["url"].strip():
            raise EndorsementSchemaError(
                f"{source}.evidence-links[{index}].url must be non-empty"
            )
        link_url = urlsplit(link["url"])
        if link_url.scheme not in {"http", "https"} or not link_url.netloc:
            raise EndorsementSchemaError(
                f"{source}.evidence-links[{index}].url must be an absolute HTTP(S) URL"
            )
    if not isinstance(record["evidence"], bool):
        raise EndorsementSchemaError(f"{source}.evidence must be a boolean")
    if record["evidence"] != bool(links):
        raise EndorsementSchemaError(
            f"{source}.evidence must be true exactly when evidence-links is non-empty"
        )

    validate_record_domains(record, source=source)

    if assessor is not None:
        expected = {
            "assessor": assessor.name,
            "assessor-id": assessor.id,
            "assessor-category": assessor.category,
            "assessor-rigor-level": assessor.rigor_level,
            "reviewType": assessor.review_type,
        }
        mismatched = [
            field for field, value in expected.items() if record[field] != value
        ]
        if mismatched:
            raise EndorsementSchemaError(
                f"{source} does not match assessor metadata for field(s): "
                + ", ".join(mismatched)
            )


def validate_endorsement_output_files(
    paths: Iterable[Path],
    *,
    expected_records: int | None = None,
    assessor: AssessorMetadata | None = None,
) -> int:
    """Validate every template record in one or more scraper output files."""

    unique_paths = tuple(dict.fromkeys(Path(path) for path in paths))
    if expected_records and not unique_paths:
        raise EndorsementSchemaError(
            "A collection scraper emitted endorsements without reporting output files"
        )
    count = 0
    for path in unique_paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EndorsementSchemaError(
                f"Cannot validate endorsement output {path}: {exc}"
            ) from exc
        records = document if isinstance(document, list) else [document]
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise EndorsementSchemaError(f"{path}[{index}] must be a JSON object")
            validate_endorsement_record(
                record,
                source=f"{path}[{index}]",
                assessor=assessor,
            )
            count += 1
    if expected_records is not None and count != expected_records:
        raise EndorsementSchemaError(
            f"Collection scraper reported {expected_records} endorsements but its "
            f"output files contain {count} records"
        )
    return count


def filter_non_endorsement_output_files(
    paths: Iterable[Path],
) -> tuple[tuple[Path, ...], int]:
    """Remove clearly non-endorsement event sessions from grouped outputs."""

    kept_paths: list[Path] = []
    removed = 0
    for path in tuple(dict.fromkeys(Path(path) for path in paths)):
        document = json.loads(path.read_text(encoding="utf-8"))
        is_array = isinstance(document, list)
        records = document if is_array else [document]
        if not all(isinstance(record, dict) for record in records):
            kept_paths.append(path)
            continue
        kept = []
        for record in records:
            if record.get("domains") == ["unknown"] and is_non_endorsement_session(
                str(record.get("label", "")),
                str(record.get("description", "")),
                str(record.get("subtitle", "")),
            ):
                removed += 1
            else:
                kept.append(record)
        if not kept:
            path.unlink(missing_ok=True)
            continue
        path.write_text(
            json.dumps(kept if is_array else kept[0], ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        kept_paths.append(path)
    return tuple(kept_paths), removed


