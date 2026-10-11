from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from typing import Any, Mapping

from .domains import detect_domains, normalize_domains
from .schema import (
    AssessorMetadata,
    build_endorsement_record,
    validate_profile_record,
)


JsonObject = dict[str, Any]


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class Request:
    """A page request emitted by a scraper."""

    url: str
    method: str = "GET"
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(self.method.upper().encode())
        digest.update(b"\0")
        digest.update(self.url.encode())
        digest.update(b"\0")
        digest.update(self.body or b"")
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class Response:
    """The response passed to a scraper's ``parse`` method."""

    request: Request
    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    fetched_at: str = field(default_factory=utc_now)

    @property
    def text(self) -> str:
        content_type = self.headers.get("Content-Type", "")
        message = Message()
        message["content-type"] = content_type
        charset = message.get_content_charset() or "utf-8"
        return self.body.decode(charset, errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


@dataclass(frozen=True, slots=True)
class Endorsement:
    """A normalized endorsement found on an assessor's website.

    ``recipient`` becomes the template's person ``name``; ``title`` becomes
    ``label``; ``description`` stores the source abstract or detailed
    evidence; ``additional_links`` stores enrichment links; ``kind`` becomes
    ``type``; and ``source_url`` becomes ``url``.
    A four-digit ``year`` (or a date/details value containing one) is required.
    ``external_id`` should be set when the source exposes a stable identifier
    such as a CVE ID. Otherwise a deterministic ID is derived from all of the
    identifying fields and ``details``. ``domains`` may be supplied explicitly;
    when omitted, the core classifier derives it from the endorsement content.
    """

    assessor_id: str
    kind: str
    title: str
    source_url: str
    description: str = ""
    additional_links: tuple[dict[str, str], ...] = ()
    recipient: str | None = None
    date: str | None = None
    year: int | None = None
    subtitle: str | None = None
    external_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    domains: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        domains = (
            normalize_domains(self.domains)
            if self.domains
            else detect_domains(
                self.kind,
                self.title,
                self.description,
                self.recipient,
                self.details,
            )
        )
        object.__setattr__(self, "domains", domains)

    @property
    def record_id(self) -> str:
        if self.external_id:
            identity: JsonObject = {
                "assessorId": self.assessor_id,
                "type": self.kind,
                "externalId": self.external_id,
            }
        else:
            identity = {
                "assessorId": self.assessor_id,
                "type": self.kind,
                "title": self.title,
                "sourceUrl": self.source_url,
                "recipient": self.recipient,
                "date": self.date,
                "year": self.year,
                "subtitle": self.subtitle,
                "details": self.details,
            }
        canonical = json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_record(self, *, assessor: AssessorMetadata) -> JsonObject:
        if not self.recipient or not self.recipient.strip():
            raise ValueError(
                f"Endorsement {self.title!r} must supply the endorsed person's name"
            )
        if not self.description.strip():
            raise ValueError(f"Endorsement {self.title!r} must supply a description")
        year = self.year or _year_from_value(self.date) or _year_from_value(
            self.details.get("year")
        )
        if year is None:
            raise ValueError(
                f"Endorsement {self.title!r} must supply a four-digit year"
            )
        subtitle = self.subtitle
        if subtitle is None:
            detail_subtitle = self.details.get("subtitle")
            subtitle = detail_subtitle if isinstance(detail_subtitle, str) else None
        return build_endorsement_record(
            name=self.recipient,
            label=self.title,
            description=self.description,
            endorsement_type=self.kind,
            assessor=assessor,
            subtitle=subtitle,
            url=self.source_url,
            additional_links=self.additional_links,
            year=year,
            domains=self.domains,
        )


@dataclass(frozen=True, slots=True)
class PersonProfile:
    """A profile fragment discovered alongside one or more endorsements."""

    name: str
    biography: str = ""
    contact: tuple[Mapping[str, str], ...] = ()

    def to_record(self) -> JsonObject:
        record = {
            "name": self.name,
            # Biography generation is deferred until the AI summarization step.
            "biography": "",
            "contact": [dict(item) for item in self.contact],
        }
        validate_profile_record(record)
        return record


def _year_from_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1000 <= value <= 9999 else None
    if isinstance(value, str):
        match = re.search(r"(?<!\d)(\d{4})(?!\d)", value)
        if match:
            return int(match.group(1))
    return None


@dataclass(frozen=True, slots=True)
class PageResult:
    """Endorsements found on a page and requests that should be followed."""

    endorsements: tuple[Endorsement, ...] = ()
    follow: tuple[Request, ...] = ()
    profiles: tuple[PersonProfile, ...] = ()

    @classmethod
    def build(
        cls,
        endorsements: Any = (),
        follow: Any = (),
        profiles: Any = (),
    ) -> PageResult:
        return cls(tuple(endorsements), tuple(follow), tuple(profiles))


