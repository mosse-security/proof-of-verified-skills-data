from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .base import BaseCollectionScraper, BaseScraper


class DiscoveryError(RuntimeError):
    pass


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True, slots=True)
class DiscoveredScrapers:
    page_scrapers: tuple[type[BaseScraper], ...]
    collection_scrapers: tuple[type[BaseCollectionScraper], ...]


def discover_scrapers(directory: Path) -> list[type[BaseScraper]]:
    """Load every concrete BaseScraper subclass below ``directory``."""

    return list(discover_all_scrapers(directory).page_scrapers)


def discover_all_scrapers(directory: Path) -> DiscoveredScrapers:
    """Load page and grouped-output scraper plugins below ``directory``."""

    directory = directory.resolve()
    if not directory.is_dir():
        raise DiscoveryError(f"Scraper directory does not exist: {directory}")

    page_classes: list[type[BaseScraper]] = []
    collection_classes: list[type[BaseCollectionScraper]] = []
    sys.path.insert(0, str(directory.parent))
    try:
        for path in sorted(directory.rglob("*.py")):
            if path.name.startswith("_") or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(directory).with_suffix("")
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", "_".join(relative.parts))
            module_name = f"_endorsement_plugin_{safe_name}_{abs(hash(path))}"
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise DiscoveryError(f"Cannot load scraper module: {path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                raise DiscoveryError(f"Failed to import {path}: {exc}") from exc

            for _, candidate in inspect.getmembers(module, inspect.isclass):
                if (
                    candidate is not BaseScraper
                    and issubclass(candidate, BaseScraper)
                    and candidate.__module__ == module.__name__
                    and not inspect.isabstract(candidate)
                ):
                    _validate(candidate, path)
                    page_classes.append(candidate)
                elif (
                    candidate is not BaseCollectionScraper
                    and issubclass(candidate, BaseCollectionScraper)
                    and candidate.__module__ == module.__name__
                    and not inspect.isabstract(candidate)
                ):
                    _validate(candidate, path)
                    collection_classes.append(candidate)
    finally:
        sys.path.pop(0)

    all_classes = [*page_classes, *collection_classes]
    duplicates = _duplicates(cls.scraper_id for cls in all_classes)
    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise DiscoveryError(f"Duplicate scraper_id values: {joined}")
    return DiscoveredScrapers(
        tuple(sorted(page_classes, key=lambda cls: cls.scraper_id)),
        tuple(sorted(collection_classes, key=lambda cls: cls.scraper_id)),
    )


def _validate(
    scraper: type[BaseScraper] | type[BaseCollectionScraper], path: Path
) -> None:
    for attribute in ("organization_id", "scraper_id"):
        value = getattr(scraper, attribute, None)
        if not isinstance(value, str) or not value.strip():
            raise DiscoveryError(
                f"{path}: {scraper.__name__}.{attribute} must be a non-empty string"
            )
        if not SAFE_ID.fullmatch(value):
            raise DiscoveryError(
                f"{path}: {scraper.__name__}.{attribute} contains unsafe "
                f"filename characters: {value!r}"
            )


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for value in values:
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return duplicate
