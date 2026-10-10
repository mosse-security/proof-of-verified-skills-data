from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .domains import normalize_domains, validate_record_domains


REQUIRED_ENDORSEMENT_FIELDS = (
    "name",
    "label",
    "type",
    "organization",
    "organization-id",
    "organization-category",
    "reviewType",
    "url",
    "year",
    "domains",
)
OPTIONAL_ENDORSEMENT_FIELDS = ("subtitle",)
ENDORSEMENT_FIELDS = (*REQUIRED_ENDORSEMENT_FIELDS, *OPTIONAL_ENDORSEMENT_FIELDS)


class EndorsementSchemaError(ValueError):
    pass


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
class OrganizationMetadata:
    """Organization fields copied into every endorsement template record."""

    id: str
    name: str
    category: str
    review_type: str

    @classmethod
    def from_file(cls, path: Path) -> OrganizationMetadata:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EndorsementSchemaError(
                f"Cannot read organization metadata from {path}: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise EndorsementSchemaError(f"{path} must contain a JSON object")

        peer_review = document.get("peerReview")
        values = {
            "id": document.get("id"),
            "name": document.get("name"),
            "category": document.get("category"),
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
                f"{path} is missing non-empty organization field(s): "
                + ", ".join(invalid)
            )
        metadata = cls(**values)
        if path.stem != metadata.id:
            raise EndorsementSchemaError(
                f"Organization file {path.name!r} contains id {metadata.id!r}"
            )
        return metadata


def build_endorsement_record(
    *,
    name: str,
    label: str,
    endorsement_type: str,
    organization: OrganizationMetadata,
    url: str,
    year: int,
    domains: Iterable[str],
    subtitle: str | None = None,
) -> dict[str, Any]:
    """Build and validate one record matching data/templates/endorsement.tpl."""

    record: dict[str, Any] = {
        "name": name,
        "label": label,
        "type": endorsement_type,
        "organization": organization.name,
        "organization-id": organization.id,
        "organization-category": organization.category,
        "reviewType": organization.review_type,
    }
    if subtitle is not None:
        record["subtitle"] = subtitle
    record.update(
        {
            "url": url,
            "year": year,
            "domains": list(normalize_domains(domains)),
        }
    )
    validate_endorsement_record(record, organization=organization)
    return record


def validate_endorsement_record(
    record: Mapping[str, Any],
    *,
    source: str = "record",
    organization: OrganizationMetadata | None = None,
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
        "type",
        "organization",
        "organization-id",
        "organization-category",
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

    validate_record_domains(record, source=source)

    if organization is not None:
        expected = {
            "organization": organization.name,
            "organization-id": organization.id,
            "organization-category": organization.category,
            "reviewType": organization.review_type,
        }
        mismatched = [
            field for field, value in expected.items() if record[field] != value
        ]
        if mismatched:
            raise EndorsementSchemaError(
                f"{source} does not match organization metadata for field(s): "
                + ", ".join(mismatched)
            )


def validate_endorsement_output_files(
    paths: Iterable[Path],
    *,
    expected_records: int | None = None,
    organization: OrganizationMetadata | None = None,
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
                organization=organization,
            )
            count += 1
    if expected_records is not None and count != expected_records:
        raise EndorsementSchemaError(
            f"Collection scraper reported {expected_records} endorsements but its "
            f"output files contain {count} records"
        )
    return count
