"""Corroborate saved LinkedIn candidates against indexed Black Hat work."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from discover_linkedin_profiles import (
    CONTACTS, SearchClient, canonical_linkedin_url, has_linkedin,
    load_local_env, write_linkedin_contact,
)


def words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def distinctive_title_in_text(title: str, text: str) -> bool:
    """Require a substantial consecutive sequence from the actual work title."""
    title_words = words(title)
    text_words = words(text)
    if len(title_words) < 5:
        return False
    length = min(len(title_words), 7)
    return any(
        title_words[i:i + length] == text_words[j:j + length]
        for i in range(len(title_words) - length + 1)
        for j in range(len(text_words) - length + 1)
    )


def result_matches_candidate(result_url: str, profile_url: str) -> bool:
    """Match an indexed profile or post to its exact LinkedIn public slug."""
    profile = canonical_linkedin_url(profile_url)
    if not profile:
        return False
    direct = canonical_linkedin_url(result_url)
    if direct:
        return direct.casefold() == profile.casefold()
    parsed = urlsplit(result_url)
    host = (parsed.hostname or '').casefold()
    if host != 'linkedin.com' and not host.endswith('.linkedin.com'):
        return False
    slug = urlsplit(profile).path.rstrip('/').split('/')[-1].casefold()
    post = re.match(r'^/posts/([^_/]+)_', parsed.path, re.IGNORECASE)
    return bool(post and post.group(1).casefold() == slug)


def corroborated(person: dict, results: list[dict]) -> list[dict]:
    matches = []
    for candidate in person.get('candidates', []):
        url = canonical_linkedin_url(candidate.get('url', ''))
        if not url:
            continue
        for result in results:
            if not result_matches_candidate(result.get('url', ''), url):
                continue
            text = result.get('title', '') + ' ' + result.get('snippet', '')
            title = next((t for t in person.get('source_records', []) if distinctive_title_in_text(t, text)), None)
            if title:
                matches.append({'url': url, 'work_title': title, 'evidence_url': result['url'],
                                'evidence_title': result.get('title', ''), 'evidence_snippet': result.get('snippet', '')})
                break
    return matches


def save(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'people': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sample', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--auto-apply', action='store_true')
    args = parser.parse_args()
    sample = json.loads(args.sample.read_text(encoding='utf-8'))['people']
    records = []
    if args.output.exists():
        records = json.loads(args.output.read_text(encoding='utf-8'))['people']
    completed = {item['slug'] for item in records}
    load_local_env()
    client = SearchClient(timeout=20)
    for person in sample:
        if person['slug'] in completed:
            continue
        contact_path = CONTACTS / f"{person['slug']}.json"
        if has_linkedin(contact_path):
            records.append({'slug': person['slug'], 'name': person['name'], 'status': 'already linked'})
            save(args.output, records)
            continue
        title = next((t for t in person.get('source_records', []) if len(words(t)) >= 5), '')
        if not title or not person.get('candidates'):
            records.append({'slug': person['slug'], 'name': person['name'], 'status': 'no candidate or searchable title'})
            save(args.output, records)
            continue
        query = f'"{person["name"].replace(chr(34), "")}" "{title.replace(chr(34), "")}" linkedin'
        print(f"[{len(records)+1}/{len(sample)}] {person['name']}", flush=True)
        results = client.search(query)
        matches = corroborated(person, results)
        unique = {match['url'] for match in matches}
        status = 'corroborated' if len(unique) == 1 else 'ambiguous' if unique else 'unconfirmed'
        record = {'slug': person['slug'], 'name': person['name'], 'query': query, 'status': status,
                  'matches': matches, 'results': results}
        if args.auto_apply and status == 'corroborated':
            record['applied'] = write_linkedin_contact(person['slug'], person['name'], next(iter(unique)))
        records.append(record)
        save(args.output, records)
    print(f"Completed {len(records)} profiles; {sum(r.get('applied', False) for r in records)} new links added.")


if __name__ == '__main__':
    main()
