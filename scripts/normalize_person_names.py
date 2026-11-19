"""Patch display casing in generated person records."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers.identity_registry import format_person_name  # noqa: E402


def record_paths() -> list[Path]:
    paths = set((ROOT / "data" / "individuals").glob("*.json"))
    paths.update((ROOT / "data" / "contact-information").glob("*.json"))
    paths.update((ROOT / "data" / "assessors").glob("**/individuals/*.json"))
    return sorted(paths)


def normalize_document(document: dict) -> bool:
    changed = False
    if isinstance(document.get("name"), str):
        normalized = format_person_name(document["name"])
        changed |= normalized != document["name"]
        document["name"] = normalized
    for endorsement in document.get("endorsements", []) or []:
        if isinstance(endorsement, dict) and isinstance(endorsement.get("name"), str):
            normalized = format_person_name(endorsement["name"])
            changed |= normalized != endorsement["name"]
            endorsement["name"] = normalized
    return changed


def main() -> None:
    changed_files = 0
    changed_names = 0
    for path in record_paths():
        document = json.loads(path.read_text(encoding="utf-8"))
        documents = document if isinstance(document, list) else [document]
        changed = False
        before = path.read_text(encoding="utf-8")
        for item in documents:
            if isinstance(item, dict):
                changed |= normalize_document(item)
        if changed:
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed_files += 1
            changed_names += sum(1 for item in documents if isinstance(item, dict) and item.get("name"))
    print(f"Normalized {changed_names} names across {changed_files} files.")


if __name__ == "__main__":
    main()
