"""Recover contact and biography data from the pre-removal individual snapshot."""

from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / ".recovery-temp" / "historical-individuals.tar"
OUTPUT = ROOT / "data" / "contact-information"
COMMIT = "a7da83a61^"


def main() -> None:
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with ARCHIVE.open("wb") as handle:
        subprocess.run(
            ["git", "archive", "--format=tar", COMMIT, "data/individuals"],
            cwd=ROOT,
            check=True,
            stdout=handle,
        )

    current = {path.name for path in (ROOT / "data" / "individuals").glob("*.json")}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    recovered = 0
    with tarfile.open(ARCHIVE) as archive:
        for member in archive.getmembers():
            if not member.name.endswith(".json"):
                continue
            slug = Path(member.name).name
            if slug not in current:
                continue
            source = json.load(archive.extractfile(member))
            contacts = [
                item
                for item in source.get("contact", []) or []
                if (item.get("url") or item.get("email"))
            ]
            if not contacts:
                continue

            recovered_data = {
                "name": source.get("name", ""),
                "contact": contacts,
            }
            biography = (source.get("biography") or "").strip()
            if biography:
                recovered_data["biography"] = biography

            destination = OUTPUT / slug
            destination.write_text(
                json.dumps(recovered_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            recovered += 1

    print(f"Recovered {recovered} contact-information files into {OUTPUT}")


if __name__ == "__main__":
    main()
