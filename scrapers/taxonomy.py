"""Shared POVS V2 classification for collected and migrated endorsements."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

BANDS = ("indirect", "observable", "independently-reviewed")
PROPERTIES = ("trusted", "production", "competition", "verifiable")
RELEASE = re.compile(
    r"\bversions?\s+(?:before |prior to |through |up to )?v?\d+\.\d+|"
    r"\b(?:before|prior to|through|up to|affects)\s+v?\d+\.\d+|"
    r"\b(?:firefox|thunderbird|chrome|kernel|windows|wordpress)\s+\d+\b|"
    r"\b(?:in|through|before)\s+[\w.-]+\s+v?\d+\.\d+", re.I,
)
REMEDIATION = re.compile(
    r"\b(?:has|have|was|were|is) (?:been )?(?:fixed(?!-length)|patched|resolved)\b|"
    r"\breleased (?:a |an )?(?:fix|patch|patched)\b|\bfixed in (?:version|release|commit|v?\d)", re.I,
)


def links_to_work(link: Mapping[str, str]) -> bool:
    """Identify inspectable work in evidence-links supplied for this endorsement."""
    url = urlsplit(link["url"])
    if url.scheme not in {"http", "https"} or not url.hostname:
        return False
    host = url.hostname.lower().removeprefix("www.").removeprefix("m.")
    parts = url.path.strip("/").split("/")
    if host in {"youtube.com", "youtube-nocookie.com"}:
        return bool((url.path == "/watch" and parse_qs(url.query).get("v"))
                    or (len(parts) == 2 and parts[0] in {"embed", "live", "shorts"} and parts[1]))
    if host == "youtu.be":
        return len(parts) == 1 and bool(parts[0])
    if host == "media.ccc.de":
        return len(parts) == 2 and parts[0] == "v" and bool(parts[1])
    if host in {"vimeo.com", "player.vimeo.com"} and any(part.isdigit() for part in parts):
        return True
    if host in {"github.com", "gitlab.com", "codeberg.org", "bitbucket.org"}:
        return len(parts) >= 2 and parts[0] not in {"orgs", "users", "search", "topics", "explore"}
    if host == "arxiv.org" and len(parts) >= 2 and parts[0] in {"abs", "pdf", "html"}:
        return True
    if re.search(r"\b(?:leaderboard|hall of fame|agenda|schedule|winners list|accepted papers list)\b",
                 link["title"], re.I):
        return False
    if url.path.lower().endswith(".pdf"):
        return True
    return bool(re.fullmatch(
        r"(?:full[- ]text(?: paper)?|(?:research )?paper|publication|(?:talk |conference )?recording|"
        r"(?:video|audio)(?: recording)?|source code|(?:code )?(?:repo|repository)|slides|technical report)",
        link["title"].strip(), re.I,
    ))


def apply_taxonomy(record: dict[str, Any]) -> None:
    kind = record["type"]
    review = record["reviewType"]
    if kind == "presentation" and review == "double_blind" and record["assessor-category"] == "conference_academic":
        record["type"] = kind = "paper"

    band = "indirect"
    competition = kind in {"competition_result", "competition_placement"}
    trusted = production = verifiable = "unknown"
    explanation = "The assessor publicly credits the individual with this achievement."
    if kind == "paper" and review == "double_blind":
        band = "independently-reviewed"
        explanation = "The proceedings credit this individual as an author of a peer-reviewed paper."
        if record["assessor-id"] == "ieee-sp" or any(urlsplit(link["url"]).path.lower().endswith(".pdf") for link in record["evidence-links"]):
            verifiable = True
    elif kind == "bug_bounty" or (
        kind == "recognition" and record["assessor-id"] == "google-security-rewards"
        and re.search(r"Public profile records [1-9]\d* awards?\b", record["description"])
    ):
        band = "independently-reviewed"
        production = trusted = True
        explanation = "The bounty programme reviewed and accepted the finding. POVS treats bounty awards as trusted production work."
    elif kind in {"cve", "vulnerability_discovery"} and re.fullmatch(r"CVE-\d{4}-\d+", record["label"], re.I):
        band = "independently-reviewed"
        explanation = "The CVE endorsement credits this individual with a reviewed vulnerability finding."
        description = record["description"]
        if RELEASE.search(description) and not re.search(r"pre.release|beta|release candidate|intentionally vulnerable", description, re.I):
            production = True
        if REMEDIATION.search(description):
            trusted = True
    elif kind == "competition_result" and review == "competition_validation":
        band = "independently-reviewed"
        production = False
        explanation = "The organiser judged the competition attempt and documented its result."
    elif kind == "presentation":
        explanation = "The conference listing credits the individual with a place on the programme."

    record["povs-taxonomy"] = {
        "evidence": band,
        "trusted": trusted,
        "production": production,
        "competition": competition,
        "verifiable": verifiable,
        "explanation": explanation,
    }

    apply_evidence_floor(record)


def has_work_link(record: Mapping[str, Any]) -> bool:
    source = urlsplit(record["url"])
    return (
        record["type"] == "presentation" and source.hostname == "media.ccc.de"
        and source.path.startswith("/v/") and len(source.path) > 3
    ) or any(links_to_work(link) for link in record["evidence-links"])


def apply_evidence_floor(record: dict[str, Any]) -> None:
    if has_work_link(record):
        taxonomy = record["povs-taxonomy"]
        taxonomy["verifiable"] = True
        if taxonomy["evidence"] == "indirect":
            taxonomy["evidence"] = "observable"
            taxonomy["explanation"] = "The cited material makes the endorsed work available for independent review."


def upgrade_legacy_endorsement(record: dict[str, Any]) -> None:
    """Accept V1 snapshots when replaying an older scrape or archive."""
    if "povs" in record and "povs-taxonomy" not in record:
        apply_taxonomy(record)
        del record["povs"]
        record.pop("evidence", None)
