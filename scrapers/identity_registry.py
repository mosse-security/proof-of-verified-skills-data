"""Centralized allow/deny/unknown handling for individual names."""
from __future__ import annotations

import threading
import json
import re
from pathlib import Path
from typing import NamedTuple


class _CachedNames(NamedTuple):
    signature: tuple[int, int]
    values: dict[str, str]


_PERSON_TITLE_PREFIX = re.compile(r"^(?:(?:dr|doctor)\.?\s+)+", re.IGNORECASE)
_MOJIBAKE_MARKERS = ("\ufffd", "Ã", "Â", "â", "ƒ")


def clean_person_name(value: str) -> str:
    """Normalize whitespace and remove academic honorifics from a name."""

    cleaned = " ".join(str(value).replace("\u00a0", " ").split()).strip()
    return _PERSON_TITLE_PREFIX.sub("", cleaned).strip()


class IdentityRegistry:
    """Resolve names against the repository's three identity lists.

    Only names in the whitelist may be persisted. Blacklisted names are
    rejected silently; unknown names are recorded once for manual review.
    Matching is case-insensitive and collapses repeated whitespace.
    """

    def __init__(self, data_directory: Path = Path("data"), assessor_id: str | None = None) -> None:
        root = Path(data_directory)
        self.data_directory = root / "assessors" / assessor_id if assessor_id else root
        self.global_whitelist_path = root / "individuals-enumeration.txt"
        self.whitelist_path = self.global_whitelist_path
        self.blacklist_path = self.data_directory / "individuals-blacklist.txt"
        self.not_validated_path = self.data_directory / "individuals-not-validated.txt"
        self._lock = threading.Lock()
        self._whitelist: _CachedNames | None = None
        self._blacklist: _CachedNames | None = None
        self._not_validated: _CachedNames | None = None
        self.data_directory.mkdir(parents=True, exist_ok=True)
        for path in (self.global_whitelist_path, self.blacklist_path, self.not_validated_path):
            path.touch(exist_ok=True)

    @classmethod
    def for_assessor(cls, assessor_id: str, data_directory: Path = Path("data")) -> "IdentityRegistry":
        return cls(data_directory, assessor_id=assessor_id)

    @staticmethod
    def normalize(name: str) -> str:
        return " ".join(clean_person_name(name).casefold().split())

    def _read(self, path: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        text = path.read_text(encoding="utf-8")
        if path == self.global_whitelist_path and any(marker in text for marker in _MOJIBAKE_MARKERS):
            raise ValueError(
                f"Global whitelist contains likely mojibake: {path}. "
                "Rewrite it as UTF-8 without a PowerShell encoding round trip."
            )
        for line in text.splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                identity = self.normalize(value)
                if path == self.global_whitelist_path and identity in result:
                    raise ValueError(
                        f"Duplicate global whitelist entry: {result[identity]!r} / {value!r}"
                    )
                result[identity] = value
        return result

    def decision(self, name: str) -> str:
        """Return ``allow``, ``deny``, or ``unknown`` for *name*."""
        identity = self.normalize(name)
        if not identity:
            return "deny"
        with self._lock:
            whitelist = self._cached(self.whitelist_path, "whitelist")
            blacklist = self._cached(self.blacklist_path, "blacklist")
            if identity in blacklist:
                return "deny"
            if identity in whitelist:
                return "allow"
            self._record_unknown_locked(name)
            return "unknown"

    def allows(self, name: str) -> bool:
        return self.decision(name) == "allow"

    def reset_not_validated(self) -> None:
        """Start a fresh review list for the current scraper run."""

        with self._lock:
            self.not_validated_path.write_text("", encoding="utf-8")
            self._not_validated = _CachedNames(
                self._signature(self.not_validated_path), {}
            )

    def filter_output_file(self, path: Path) -> int:
        """Remove non-whitelisted records from a grouped JSON output file."""
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if not isinstance(document, list):
            return 0
        kept = []
        removed = 0
        for record in document:
            name = record.get("name") if isinstance(record, dict) else None
            if isinstance(name, str) and not self.allows(name):
                removed += 1
            else:
                kept.append(record)
        if removed:
            path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return removed

    def _record_unknown_locked(self, name: str) -> None:
        value = clean_person_name(name)
        if not value:
            return
        existing = self._cached(self.not_validated_path, "not_validated")
        identity = self.normalize(value)
        if identity not in existing:
            with self.not_validated_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(value + "\n")
            # Keep this registry's in-memory view coherent without waiting
            # for filesystem timestamp resolution.
            existing[identity] = value
            self._not_validated = _CachedNames(
                self._signature(self.not_validated_path), existing
            )

    def _cached(self, path: Path, attribute: str) -> dict[str, str]:
        signature = self._signature(path)
        cached = getattr(self, f"_{attribute}")
        if cached is None or cached.signature != signature:
            cached = _CachedNames(signature, self._read(path))
            setattr(self, f"_{attribute}", cached)
        return cached.values

    @staticmethod
    def _signature(path: Path) -> tuple[int, int]:
        try:
            stat = path.stat()
        except OSError:
            return (0, 0)
        return (stat.st_mtime_ns, stat.st_size)
