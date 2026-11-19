"""Apply the repository's explicit person-level POVS tags.

Tags are stored on individual records, not endorsements.  This module is
deliberately separate from challenge matching: it only maintains the manual
classification tags that the frontend reads.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


CVE_RE = re.compile(r"^CVE-\d{4}-\d+$", re.IGNORECASE)
WINNING_AWARD_RE = re.compile(r"grand prize|winner|best\s|runner", re.IGNORECASE)
ACADEMIC_JOURNAL_ASSESSOR_IDS = {
    "computers-and-security",
    "ieee-tifs",
    "journal-of-cybersecurity",
}
ACADEMIC_ASSESSOR_CATEGORIES = {
    "academic_journal",
    "conference_academic",
}
THREAT_RESEARCH_DOMAINS = {
    "digital-forensics",
    "incident-response",
    "threat-hunting",
    "cybercrime-and-fraud",
}


def tags_for_person(endorsements: list[dict], existing: list[str] | None = None) -> list[str]:
    """Return person-level tags, preserving any tags not owned by this module."""

    tags = {tag for tag in (existing or []) if isinstance(tag, str) and tag.strip()}
    for endorsement in endorsements:
        if endorsement.get("assessor-id") == "sans-holiday-hack":
            tags.add("ctf-participant")
            if WINNING_AWARD_RE.search(str(endorsement.get("subtitle", ""))):
                tags.add("ctf-champion")

        if CVE_RE.fullmatch(str(endorsement.get("label", ""))):
            tags.add("cve-researcher")
            cve_text = " ".join(
                str(endorsement.get(field, ""))
                for field in ("label", "subtitle", "description")
            )
            if re.search(r"severity\s*:\s*critical", cve_text, re.IGNORECASE):
                tags.add("critical-cve-discovery")

        if endorsement.get("type") == "bug_bounty":
            tags.add("bounty-hunter")

        if endorsement.get("type") == "presentation":
            tags.add("top-conference-speaker")

        if (
            endorsement.get("assessor-id") in ACADEMIC_JOURNAL_ASSESSOR_IDS
            or endorsement.get("assessor-category") in ACADEMIC_ASSESSOR_CATEGORIES
        ):
            tags.add("academic-researcher")

        if endorsement.get("assessor-id") == "pwn2own":
            tags.add("leaderboard-elite")

        if THREAT_RESEARCH_DOMAINS.intersection(endorsement.get("domains", [])):
            tags.add("threat-researcher")

    return sorted(tags)


def apply_tags(directory: Path = Path("data/individuals")) -> int:
    changed = 0
    for path in sorted(directory.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        tags = tags_for_person(document.get("endorsements", []), document.get("tags", []))
        if tags != document.get("tags", []):
            document["tags"] = tags
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    return changed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/individuals"))
    args = parser.parse_args()
    print(f"Updated tagged individual records: {apply_tags(args.directory)}")
