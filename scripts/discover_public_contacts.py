"""Discover corroborated public contact links from search-engine results."""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from discover_linkedin_profiles import CONTACTS, ROOT, SearchClient, load_local_env, people_for_assessor
from corroborate_linkedin_sample import distinctive_title_in_text


def classify_url(value: str, name: str) -> tuple[str, str] | None:
    parsed = urlsplit(value)
    host = (parsed.hostname or '').casefold().removeprefix('www.')
    if parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password:
        return None
    parts = [part for part in parsed.path.split('/') if part]
    if host == 'linkedin.com' or host.endswith('.linkedin.com'):
        if len(parts) >= 2 and parts[0].casefold() == 'in' and re.fullmatch(r'[\w%-]+', parts[1]):
            return 'linkedin', f'https://www.linkedin.com/in/{parts[1]}'
        if len(parts) >= 2 and parts[0].casefold() == 'posts':
            slug = parts[1].split('_', 1)[0]
            if '_' in parts[1] and re.fullmatch(r'[\w%-]+', slug):
                return 'linkedin', f'https://www.linkedin.com/in/{slug}'
        return None
    if host in ('x.com', 'twitter.com', 'mobile.twitter.com'):
        if parts and re.fullmatch(r'[A-Za-z0-9_]{1,15}', parts[0]) and parts[0].casefold() not in {'home', 'search', 'intent', 'share', 'i'}:
            return 'twitter', f'https://x.com/{parts[0]}'
        return None
    # Restrict automatic personal sites to a root page on a name-based domain.
    if parts or parsed.query or host.count('.') != 1:
        return None
    name_key = ''.join(re.findall(r'[a-z0-9]+', name.casefold()))
    host_key = re.sub(r'[^a-z0-9]', '', host.split('.')[0])
    if len(name_key) >= 8 and host_key == name_key:
        return 'website', urlunsplit(('https', host, '/', '', ''))
    return None


def corroborated_links(person: dict, results: list[dict]) -> list[dict]:
    links = {}
    titles = person.get('source_records', [])
    for result in results:
        classified = classify_url(result.get('url', ''), person['name'])
        if not classified:
            continue
        title_words = set(re.findall(r'[a-z0-9]+', result.get('title', '').casefold()))
        name_words = [w for w in re.findall(r'[a-z0-9]+', person['name'].casefold()) if len(w) > 1]
        if len(name_words) < 2 or not all(w in title_words for w in name_words):
            continue
        text = result.get('title', '') + ' ' + result.get('snippet', '')
        title = next((t for t in titles if distinctive_title_in_text(t, text)), None)
        if title:
            label, url = classified
            links[url.casefold()] = {'label': label, 'url': url, 'evidence_url': result['url'],
                                     'work_title': title, 'snippet': result.get('snippet', '')}
    return list(links.values())


def add_contact(person: dict, link: dict) -> bool:
    path = CONTACTS / f"{person['slug']}.json"
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'name': person['name'], 'contact': []}
    contacts = data.setdefault('contact', [])
    if any(c.get('url', '').rstrip('/').casefold() == link['url'].rstrip('/').casefold() for c in contacts):
        return False
    # Do not replace an existing account of the same social-network type.
    if link['label'] in ('linkedin', 'twitter') and any(c.get('label', '').casefold() in ({'linkedin'} if link['label'] == 'linkedin' else {'twitter', 'x'}) for c in contacts):
        return False
    contacts.append({'label': link['label'], 'url': link['url'], 'source': 'povs-public-contact-discovery'})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--sample', type=Path, help='Existing assessor sample JSON; preserves its original cohort.')
    source.add_argument('--assessor', help='Assessor ID to search for people without a LinkedIn contact.')
    parser.add_argument('--output', type=Path, required=True, help='Checkpoint/audit JSON in an ignored local directory.')
    parser.add_argument('--auto-apply', action='store_true')
    parser.add_argument('--limit', type=int, help='Limit the number of people in the sample.')
    parser.add_argument('--workers', type=int, default=8, help='Maximum concurrent people to search (default: 8).')
    args = parser.parse_args()
    people = json.loads(args.sample.read_text(encoding='utf-8'))['people'] if args.sample else people_for_assessor(args.assessor)
    if args.limit is not None:
        if args.limit < 1:
            parser.error('--limit must be positive')
        people = people[:args.limit]
    records = json.loads(args.output.read_text(encoding='utf-8'))['people'] if args.output.exists() else []
    completed = {r['slug'] for r in records}
    load_local_env()
    client = SearchClient(timeout=20)
    if not 1 <= args.workers <= 16:
        parser.error('--workers must be between 1 and 16')
    def search_person(person: dict) -> tuple[dict, str, list[dict]]:
        name = person['name'].replace('"', '')
        query = f'"{name}" cybersecurity'
        def search_with_retry(value: str) -> list[dict]:
            for attempt in range(3):
                try:
                    return client.search(value)
                except (OSError, RuntimeError, ValueError):
                    if attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
            return []
        results = search_with_retry(query)
        work = next((t for t in person.get('source_records', []) if len(re.findall(r'[a-z0-9]+', t.casefold())) >= 5), '')
        if work:
            work_query = f'"{name}" "{work.replace(chr(34), "")}"'
            results.extend(search_with_retry(work_query))
        return person, query, results

    pending = [person for person in people if person['slug'] not in completed]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
      futures = {executor.submit(search_person, person): person for person in pending}
      for future in as_completed(futures):
        try:
            person, query, results = future.result()
        except (OSError, RuntimeError, ValueError) as error:
            print(f"Search failed for {futures[future]['name']}: {error}", flush=True)
            continue
        links = corroborated_links(person, results)
        applied = [link['url'] for link in links if args.auto_apply and add_contact(person, link)]
        records.append({'slug': person['slug'], 'name': person['name'], 'query': query,
                        'links': links, 'applied': applied, 'results': results})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'people': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"[{len(records)}/{len(people)}] Searched: {person['name']}", flush=True)
    print(f"Completed {len(records)} people; added {sum(len(r['applied']) for r in records)} links.")


if __name__ == '__main__':
    main()
