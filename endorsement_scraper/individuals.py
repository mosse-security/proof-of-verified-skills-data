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
from pathlib import Path
from typing import Any

from .schema import validate_endorsement_record


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
    endorsements_directory: Path = Path("data/tmp/endorsements"),
    output_directory: Path = Path("data/individuals"),
    *,
    overwrite: bool = True,
    profiles_directory: Path = Path("data/tmp/profiles"),
) -> IndividualMergeResult:
    """Merge all endorsement records into one template-shaped file per person."""

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
            identity = _person_identity(name)
            person = grouped.setdefault(identity, {"name": name, "records": {}})
            person.setdefault("profiles", []).append(profile)

    output_directory.mkdir(parents=True, exist_ok=True)
    used_paths: dict[str, str] = {}
    files: list[Path] = []
    created = overwritten = skipped = 0
    total = 0
    for identity, person in sorted(grouped.items(), key=lambda item: item[0]):
        records = sorted(person["records"].values(), key=_endorsement_sort_key)
        total += len(records)
        filename = _individual_filename(person["name"], identity, used_paths)
        path = output_directory / filename
        payload = {
            "name": person["name"],
            "biography": "",
            "contact": _merged_contacts(person.get("profiles", [])),
            "endorsements": records,
        }
        _validate_individual(payload, source=str(path))
        if path.exists() and not overwrite:
            skipped += 1
        else:
            existed = path.exists()
            _atomic_write(
                path,
                (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
            overwritten += int(existed)
            created += int(not existed)
        files.append(path)

    return IndividualMergeResult(
        people=len(grouped),
        endorsements=total,
        created=created,
        overwritten=overwritten,
        skipped=skipped,
        files=tuple(files),
    )


def _validate_individual(document: dict[str, Any], *, source: str) -> None:
    expected = {"name", "biography", "contact", "endorsements"}
    if set(document) != expected:
        raise IndividualMergeError(f"{source} must contain exactly {sorted(expected)}")
    if not isinstance(document["name"], str) or not document["name"].strip():
        raise IndividualMergeError(f"{source}.name must be a non-empty string")
    if not isinstance(document["biography"], str):
        raise IndividualMergeError(f"{source}.biography must be a string")
    if not isinstance(document["contact"], list):
        raise IndividualMergeError(f"{source}.contact must be an array")
    if not isinstance(document["endorsements"], list):
        raise IndividualMergeError(f"{source}.endorsements must be an array")
    for index, endorsement in enumerate(document["endorsements"]):
        validate_endorsement_record(endorsement, source=f"{source}.endorsements[{index}]")


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
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()


def _person_identity(name: str) -> str:
    return " ".join(name.casefold().split())


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
    parser.add_argument("--endorsements-dir", type=Path, default=Path("data/tmp/endorsements"))
    parser.add_argument("--profiles-dir", type=Path, default=Path("data/tmp/profiles"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/individuals"))
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
        result = merge_endorsements(
            args.endorsements_dir,
            args.output_dir,
            overwrite=args.overwrite,
            profiles_directory=args.profiles_dir,
        )
    except (OSError, IndividualMergeError) as exc:
        print(f"Individual merge failed: {exc}")
        return 1
    print(
        f"Individuals: people={result.people} endorsements={result.endorsements} "
        f"created={result.created} overwritten={result.overwritten} skipped={result.skipped}"
    )
    if not args.keep_tmp:
        removed = cleanup_generated_directory(args.endorsements_dir)
        removed += cleanup_generated_directory(args.profiles_dir)
        print(f"Cleaned temporary output entries: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


