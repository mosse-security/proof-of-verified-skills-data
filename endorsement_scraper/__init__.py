"""Public API for assessor endorsement scrapers."""

from .base import (
    BaseCollectionScraper,
    BaseScraper,
    CollectionScraperContext,
    CollectionScraperResult,
)
from .models import Endorsement, PageResult, PersonProfile, Request, Response
from .domains import (
    ALLOWED_DOMAINS,
    CYBER_DOMAINS,
    UNKNOWN_DOMAIN,
    detect_domains,
    normalize_domains,
)
from .schema import (
    ENDORSEMENT_FIELDS,
    OPTIONAL_ENDORSEMENT_FIELDS,
    REQUIRED_ENDORSEMENT_FIELDS,
    EndorsementSchemaError,
    AssessorMetadata,
    build_endorsement_record,
    validate_endorsement_record,
    validate_profile_record,
)

__all__ = [
    "BaseScraper",
    "BaseCollectionScraper",
    "CollectionScraperContext",
    "CollectionScraperResult",
    "Endorsement",
    "PersonProfile",
    "PageResult",
    "Request",
    "Response",
    "ALLOWED_DOMAINS",
    "CYBER_DOMAINS",
    "UNKNOWN_DOMAIN",
    "detect_domains",
    "normalize_domains",
    "ENDORSEMENT_FIELDS",
    "OPTIONAL_ENDORSEMENT_FIELDS",
    "REQUIRED_ENDORSEMENT_FIELDS",
    "EndorsementSchemaError",
    "AssessorMetadata",
    "build_endorsement_record",
    "validate_endorsement_record",
    "validate_profile_record",
]


