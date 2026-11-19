"""Merge contact links captured by assessor scrapers into contact-information."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
INDIVIDUALS = ROOT / "data" / "individuals"
CONTACTS = ROOT / "data" / "contact-information"


def label_for(contact: dict[str, str]) -> str:
    if contact.get("email"):
        return "email"
    host = urlparse(contact.get("url", "")).netloc.casefold().removeprefix("www.")
    if host.endswith("linkedin.com"):
        return "linkedin"
    if host in {"twitter.com", "x.com"} or host.endswith("twitter.com"):
        return "twitter"
    if host.endswith("github.com"):
        return "github"
    if host.endswith("facebook.com") or host == "fb.com":
        return "facebook"
    if host.endswith("youtube.com") or host == "youtu.be":
        return "youtube"
    if host.endswith("instagram.com"):
        return "instagram"
    if host.endswith("mastodon.social") or host.endswith("infosec.exchange"):
        return "mastodon"
    if host in {"bsky.app", "bsky.social"}:
        return "bluesky"
    if host.endswith("hackerone.com"):
        return "hackerone"
    if host.endswith("bugcrowd.com"):
        return "bugcrowd"
    return contact.get("label", "website") or "website"


def key_for(contact: dict[str, str]) -> tuple[str, str]:
    if contact.get("email"):
        return ("email", contact["email"].strip().casefold())
    return ("url", contact.get("url", "").strip().rstrip("/").casefold())


def main() -> None:
    current = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in INDIVIDUALS.glob("*.json")
    }
    assessor_contacts: dict[str, list[dict[str, str]]] = {}
    for path in (ROOT / "data" / "assessors").glob("**/individuals/*.json"):
        person = json.loads(path.read_text(encoding="utf-8"))
        if path.stem not in current:
            continue
        for raw_contact in person.get("contact", []) or []:
            contact = {
                field: str(raw_contact[field]).strip()
                for field in ("label", "url", "email")
                if raw_contact.get(field)
            }
            if contact.get("url") or contact.get("email"):
                contact["label"] = label_for(contact)
                assessor_contacts.setdefault(path.stem, []).append(contact)

    CONTACTS.mkdir(parents=True, exist_ok=True)
    created = 0
    updated = 0
    added_contacts = 0
    for slug, contacts in assessor_contacts.items():
        destination = CONTACTS / f"{slug}.json"
        existing = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {
            "name": current[slug]["name"],
            "contact": [],
        }
        merged = list(existing.get("contact", []) or [])
        keys = {key_for(item) for item in merged}
        for contact in contacts:
            key = key_for(contact)
            if key not in keys:
                merged.append(contact)
                keys.add(key)
                added_contacts += 1
        if not destination.exists():
            created += 1
        elif merged != existing.get("contact", []):
            updated += 1
        existing["contact"] = merged
        destination.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(
        f"Processed {len(assessor_contacts)} people; created {created}, "
        f"updated {updated}, added {added_contacts} contacts."
    )


if __name__ == "__main__":
    main()
