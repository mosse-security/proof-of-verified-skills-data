"""Format-neutral archive storage for cached scraper source documents.

The scraper consumes bytes through this interface, so adding CSV/XLSX readers
later does not require changing path or ZIP handling in individual scrapers.
"""

from __future__ import annotations

import os
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath


class ArchiveStore:
    """Read and write source documents from a directory or ZIP archive."""

    def __init__(self, location: Path) -> None:
        self.location = Path(location)
        self._lock = threading.RLock()

    def read(self, member: str) -> bytes | None:
        member = _member_name(member)
        with self._lock:
            if self.location.is_dir():
                path = self.location.joinpath(*PurePosixPath(member).parts)
                return path.read_bytes() if path.is_file() else None
            if self.location.suffix.casefold() == ".zip" and self.location.is_file():
                with zipfile.ZipFile(self.location) as archive:
                    try:
                        return archive.read(member)
                    except KeyError:
                        return None
            return None

    def write(self, member: str, content: bytes) -> None:
        member = _member_name(member)
        with self._lock:
            if self.location.suffix.casefold() != ".zip":
                path = self.location.joinpath(*PurePosixPath(member).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write(path, content)
                return

            self.location.parent.mkdir(parents=True, exist_ok=True)
            temporary_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self.location.parent,
                    prefix=f".{self.location.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    temporary_name = temporary.name
                with zipfile.ZipFile(temporary_name, "w", zipfile.ZIP_DEFLATED) as target:
                    if self.location.is_file():
                        with zipfile.ZipFile(self.location) as source:
                            for info in source.infolist():
                                if info.filename != member:
                                    target.writestr(info, source.read(info.filename))
                    target.writestr(member, content)
                os.replace(temporary_name, self.location)
                temporary_name = None
            finally:
                if temporary_name and os.path.exists(temporary_name):
                    os.unlink(temporary_name)


def _member_name(member: str) -> str:
    path = PurePosixPath(member)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive member: {member!r}")
    return path.as_posix()


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
