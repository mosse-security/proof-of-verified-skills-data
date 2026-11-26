"""Find high-confidence LinkedIn profiles for records from a chosen assessor.

The script searches a supported search API for public result metadata only. It
never visits LinkedIn, never writes API keys to disk, and never changes a
contact record unless a reviewer explicitly approves a candidate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
INDIVIDUALS = ROOT / "data" / "individuals"
CONTACTS = ROOT / "data" / "contact-information"


def load_local_env() -> None:
    """Load a minimal .env file without overwriting real environment values."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


def canonical_linkedin_url(value: str) -> str | None:
    """Accept only a public personal LinkedIn profile URL; remove tracking data."""
    parsed = urlsplit(value.strip())
    host = parsed.netloc.casefold().removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]
    if not (host.endswith("linkedin.com") and len(parts) >= 2 and parts[0].casefold() == "in"):
        return None
    return urlunsplit(("https", "www.linkedin.com", f"/in/{parts[1]}", "", ""))


def has_linkedin(contact_path: Path) -> bool:
    if not contact_path.exists():
        return False
    person = json.loads(contact_path.read_text(encoding="utf-8"))
    return any(canonical_linkedin_url(str(item.get("url", ""))) for item in person.get("contact", []))


def people_for_assessor(assessor_id: str) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    for path in sorted(INDIVIDUALS.glob("*.json")):
        person = json.loads(path.read_text(encoding="utf-8"))
        source_records = [
            endorsement.get("label") or endorsement.get("description") or ""
            for endorsement in person.get("endorsements", [])
            if endorsement.get("assessor-id") == assessor_id
        ]
        if source_records and not has_linkedin(CONTACTS / path.name):
            people.append({
                "slug": path.stem,
                "name": person["name"],
                "assessor_id": assessor_id,
                "source_records": source_records,
            })
    return people


def linkedin_query_for(person: dict[str, Any]) -> str:
    name = person["name"].replace('"', "")
    return f'site:linkedin.com "{name}" AND "Cyber"'


class SearchClient:
    def __init__(self, timeout: int = 15) -> None:
        self.serper_key = os.environ.get("SERPER_API_KEY")
        self.google_key = os.environ.get("GOOGLE_CSE_API_KEY")
        self.google_cx = os.environ.get("GOOGLE_CSE_ID")
        self.timeout = timeout
        if not self.serper_key and not (self.google_key and self.google_cx):
            raise RuntimeError(
                "Configure SERPER_API_KEY (recommended) or both GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID. "
                "Put placeholders in .env.example and real values only in the ignored .env file."
            )

    @property
    def provider(self) -> str:
        return "serper" if self.serper_key else "google-cse"

    def search(self, query: str) -> list[dict[str, str]]:
        if self.serper_key:
            request = Request(
                "https://google.serper.dev/search",
                data=json.dumps({"q": query, "num": 10}).encode("utf-8"),
                headers={
                    "X-API-KEY": self.serper_key,
                    "Content-Type": "application/json",
                    "User-Agent": "POVS-LinkedIn-Discovery/1.0",
                },
                method="POST",
            )
            data = self._request_json(request)
            results = data.get("organic", [])
            return [self._result(item) for item in results]

        params = urlencode({"key": self.google_key, "cx": self.google_cx, "q": query, "num": 10})
        request = Request(f"https://www.googleapis.com/customsearch/v1?{params}")
        data = self._request_json(request)
        return [self._result(item) for item in data.get("items", [])]

    @staticmethod
    def _result(item: dict[str, Any]) -> dict[str, str]:
        return {
            "url": str(item.get("link", "")),
            "title": str(item.get("title", "")),
            "snippet": str(item.get("snippet", "")),
        }

    def _request_json(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"Search provider returned HTTP {error.code}; the API key was not logged.") from None
        except URLError as error:
            raise RuntimeError(f"Could not reach the search provider: {error.reason}") from None


def candidates_for(results: list[dict[str, str]], name: str) -> list[dict[str, Any]]:
    name_terms = {term.casefold() for term in name.split() if len(term) > 1}
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in results:
        url = canonical_linkedin_url(result["url"])
        if not url or url in seen:
            continue
        seen.add(url)
        text = f'{result["title"]} {result["snippet"]}'.casefold()
        matched_terms = sum(term in text for term in name_terms)
        candidates.append({
            **result,
            "url": url,
            "name_terms_matched": matched_terms,
            "cybersecurity_context": any(term in text for term in (
                "cybersecurity", "cyber security", "information security", "infosec",
                "security engineer", "security researcher", "penetration test",
                "red team", "blue team", "threat intelligence",
            )),
        })
    return candidates


def high_confidence_url(name: str, candidates: list[dict[str, Any]]) -> tuple[str | None, str]:
    """Return a URL only when the simple cyber-focused search is unambiguous."""
    required_terms = len({term.casefold() for term in name.split() if len(term) > 1})
    name_matches = {
        candidate["url"]
        for candidate in candidates
        if candidate["name_terms_matched"] >= required_terms
    }
    if len(name_matches) != 1:
        return None, "the name is not unique in the LinkedIn search results"
    cyber_matches = {
        candidate["url"]
        for candidate in candidates
        if candidate["name_terms_matched"] >= required_terms and candidate["cybersecurity_context"]
    }
    if cyber_matches == name_matches:
        return next(iter(name_matches)), "the sole full-name LinkedIn profile has an explicit cybersecurity signal"
    if not cyber_matches:
        return None, "no full-name cybersecurity profile was returned by the search"
    return None, "the sole full-name profile did not have an explicit cybersecurity signal"


def write_linkedin_contact(slug: str, name: str, url: str) -> bool:
    destination = CONTACTS / f"{slug}.json"
    existing = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {
        "name": name, "contact": []
    }
    contacts = list(existing.get("contact", []))
    if any(canonical_linkedin_url(str(item.get("url", ""))) for item in contacts):
        return False
    contacts.append({
        "label": "linkedin",
        "url": url,
        "source": "povs-linkedin-discovery",
    })
    existing["contact"] = contacts
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def write_audit(output: Path, provider: str, people: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"provider": provider, "people": people}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def discover(args: argparse.Namespace) -> None:
    load_local_env()
    client = SearchClient(timeout=args.timeout)
    people = people_for_assessor(args.assessor)
    if args.offset:
        people = people[args.offset:]
    if args.limit:
        people = people[:args.limit]
    output = (args.output or ROOT / "tmp" / f"linkedin-candidates-{args.assessor}.json").resolve()
    review: list[dict[str, Any]] = []
    auto_applied = 0
    for index, person in enumerate(people, start=1):
        query = linkedin_query_for(person)
        print(f"[{index}/{len(people)}] Searching LinkedIn: {person['name']}", flush=True)
        candidates = candidates_for(client.search(query), person["name"])
        selected_url, reason = high_confidence_url(person["name"], candidates)
        automatic_review = {
            "eligible": selected_url is not None,
            "selected_url": selected_url,
            "reason": reason,
        }
        if args.auto_apply and selected_url and write_linkedin_contact(person["slug"], person["name"], selected_url):
            auto_applied += 1
            automatic_review["applied"] = True
        review.append({
            **person,
            "query": query,
            "candidates": candidates,
            "automatic_review": automatic_review,
            "review": {"approved": False, "selected_url": None},
        })
        write_audit(output, client.provider, review)
        print(f"[{index}/{len(people)}] {person['name']}")

    print(f"Wrote {len(review)} review records to {output.relative_to(ROOT)}")
    if args.auto_apply:
        print(f"Applied {auto_applied} high-confidence links directly to contact information.")
    print("Lower-confidence candidates remain in the review file and require explicit approval before using --apply.")


def apply_approved(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    people = payload.get("people", [])
    applied = 0
    skipped = 0
    for person in people:
        review = person.get("review", {})
        url = canonical_linkedin_url(str(review.get("selected_url") or ""))
        if not review.get("approved") or not url:
            skipped += 1
            continue
        candidate_urls = {
            canonical_linkedin_url(str(candidate.get("url", "")))
            for candidate in person.get("candidates", [])
        }
        if url not in candidate_urls:
            skipped += 1
            continue
        if write_linkedin_contact(person["slug"], person["name"], url):
            applied += 1
        else:
            skipped += 1
    print(f"Applied {applied} approved LinkedIn links; skipped {skipped} unapproved or already-linked records.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessor", required=True, help="Assessor ID whose people to process, e.g. grrcon.")
    parser.add_argument("--output", type=Path, help="Ignored local review JSON path.")
    parser.add_argument("--limit", type=int, help="Process only the first N eligible people.")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first N eligible people; useful for smaller batches.")
    parser.add_argument("--auto-apply", action="store_true", help="Write only unambiguous full-name cybersecurity profiles.")
    parser.add_argument("--timeout", type=int, default=15, help="Maximum seconds to wait for each provider request (default: 15).")
    parser.add_argument("--apply", type=Path, metavar="REVIEW_JSON", help="Apply only explicitly approved candidates.")
    args = parser.parse_args()
    try:
        if args.apply:
            apply_approved(args.apply.resolve())
        else:
            discover(args)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
