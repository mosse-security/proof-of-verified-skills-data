"""Find contact candidates corroborated by independent saved search results.

This produces a review queue only: shared biographical details are useful clues,
not proof that similarly named people are the same individual.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from discover_public_contacts import classify_url

COMMON = set('about account across after american analysis analyst andrew another application applications approach artificial association attack attacks author background blackhat black conference consulting corporation cryptography cybersecurity developer development director education engineering enterprise experience expert federal founder global government information institute intelligence international linkedin machine management manager member microsoft network offensive organization platform privacy professional profile professor project protection public research researcher researchers researchgate school science security services software speaker specialist systems technical technology technologies university united using vulnerabilities vulnerability website working works officer scientist consultant architect center practitioner'.split())
EXCLUDED_HOSTS = ('linkedin.com', 'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 'researchgate.net', 'semanticscholar.org', 'vetted-cyber-talent.com')


def tokens(text: str) -> set[str]:
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().casefold()
    return set(re.findall(r'[a-z0-9]+', text))


def name_in_title(name: str, title: str) -> bool:
    required = {w for w in tokens(name) if len(w) > 1}
    return len(required) >= 2 and required <= tokens(title)


def ranked_candidates(person: dict) -> list[dict]:
    results = person.get('results', [])
    name = person['name']
    name_tokens = tokens(name)
    candidates = []
    for result in results:
        classified = classify_url(result.get('url', ''), name)
        if not classified or not name_in_title(name, result.get('title', '')):
            continue
        label, url = classified
        # A LinkedIn post can mention a speaker while belonging to someone else.
        if label == 'linkedin' and '/in/' not in urlsplit(result.get('url', '')).path.casefold():
            continue
        normalized_title = re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', result.get('title', '')).encode('ascii', 'ignore').decode().casefold()).strip()
        normalized_name = re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().casefold()).strip()
        if label == 'linkedin' and not re.match(r'^(?:(?:dr|prof|professor|ing)\s+)*' + re.escape(normalized_name) + r'(?:\s|$)', normalized_title):
            continue
        candidate_tokens = {w for w in tokens(result.get('title', '') + ' ' + result.get('snippet', ''))
                            if len(w) >= 6 and w not in COMMON and w not in name_tokens and not w.isdigit()}
        evidence = []
        for other in results:
            host = (urlsplit(other.get('url', '')).hostname or '').casefold()
            candidate_host = (urlsplit(result.get('url', '')).hostname or '').casefold()
            if host.removeprefix('www.') == candidate_host.removeprefix('www.'):
                continue
            if not host or any(host == h or host.endswith('.' + h) for h in EXCLUDED_HOSTS):
                continue
            if not name_in_title(name, other.get('title', '')):
                continue
            overlap = sorted(candidate_tokens & tokens(other.get('title', '') + ' ' + other.get('snippet', '')))
            if overlap:
                evidence.append({'url': other['url'], 'title': other.get('title', ''),
                                 'snippet': other.get('snippet', ''), 'shared_terms': overlap})
        if evidence:
            candidates.append({'label': label, 'url': url, 'title': result.get('title', ''),
                               'snippet': result.get('snippet', ''), 'evidence': evidence})
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding='utf-8'))
    queue = []
    for person in audit['people']:
        candidates = ranked_candidates(person)
        if candidates:
            queue.append({'slug': person['slug'], 'name': person['name'], 'candidates': candidates})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'people': queue}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"{len(queue)} people have candidates sharing distinctive terms with another named search result; review required.")


if __name__ == '__main__':
    main()
