from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .models import Endorsement
from .schema import (
    AssessorMetadata,
    validate_endorsement_record,
    validate_profile_record,
)


WriteStatus = Literal["created", "skipped", "overwritten"]
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True, slots=True)
class WriteResult:
    path: Path
    status: WriteStatus


class EndorsementStore:
    """Thread-safe, atomic JSON record storage."""

    def __init__(
        self,
        directory: Path,
        assessors_directory: Path = Path("data/assessors"),
    ) -> None:
        self.directory = directory
        self.assessors_directory = assessors_directory
        self._lock = threading.Lock()
        self._assessors: dict[str, AssessorMetadata] = {}

    def save(
        self,
        endorsement: Endorsement,
        *,
        scraper_id: str,
        overwrite: bool,
    ) -> WriteResult:
        _validate_component(endorsement.assessor_id, "assessor_id")
        assessor = self.assessor_metadata(endorsement.assessor_id)
        record = endorsement.to_record(assessor=assessor)
        validate_endorsement_record(record, assessor=assessor)
        path = (
            self.directory
            / endorsement.assessor_id
            / f"{endorsement.record_id}.json"
        )
        serialized = (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode()

        with self._lock:
            existed = path.exists()
            if existed and not overwrite:
                return WriteResult(path, "skipped")
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, serialized)
            return WriteResult(path, "overwritten" if existed else "created")

    def assessor_metadata(self, assessor_id: str) -> AssessorMetadata:
        """Load and cache the authoritative assessor template fields."""

        with self._lock:
            cached = self._assessors.get(assessor_id)
            if cached is None:
                cached = AssessorMetadata.from_file(
                    self.assessors_directory / f"{assessor_id}.json"
                )
                self._assessors[assessor_id] = cached
            return cached


class ProfileStore:
    """Atomic storage for profile fragments emitted by standard scrapers."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = threading.Lock()

    def save(
        self,
        profile: "PersonProfile",
        *,
        assessor_id: str,
        scraper_id: str,
    ) -> Path:
        from .models import PersonProfile

        if not isinstance(profile, PersonProfile):
            raise TypeError(f"Expected PersonProfile, got {type(profile).__name__}")
        _validate_component(assessor_id, "assessor_id")
        _validate_component(scraper_id, "scraper_id")
        record = profile.to_record()
        identity = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        path = self.directory / assessor_id / scraper_id / f"{digest}.json"
        serialized = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode()
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                _atomic_write(path, serialized)
        return path


def _validate_component(value: str, label: str) -> None:
    if not SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"Unsafe {label}: {value!r}")


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


