"""Map published record URLs to configured pages using archived page links.

Run after changing records, source lists, or archived pages. This does not fetch
the network or infer provenance from years or organization names.
"""
from collections import defaultdict
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit
from zipfile import ZipFile

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'


def member_candidates(assessor, url):
    path = urlsplit(url).path.strip('/')
    if assessor == 'rsa-conference':
        from scrapers.assessors.rsa_conference import rsa_year
        try:
            yield f'us{rsa_year(url) % 100:02d}-rendered.html'
        except ValueError:
            pass
    yield path
    yield path.replace('https://', 'https:/').replace('http://', 'http:/')
    yield path + '/index.html'
    if assessor == 'def-con':
        import re
        match = re.search(r'defcon-(\d+|safemode)', path)
        if match:
            yield f'defcon-{match.group(1)}/speakers.html'
    if assessor == 'ieee-sp':
        yield Path(path).name
    if assessor == 'mozilla-security':
        yield 'hall-of-fame.html'
    if assessor == 'pwn2own':
        yield 'blog_tag-Pwn2Own.html'
    if assessor == 'sans-holiday-hack':
        yield 'winners-and-answers.html'


def main():
    source_urls = defaultdict(set)
    for path in (DATA / 'individuals').glob('*.json'):
        person = json.loads(path.read_text(encoding='utf-8'))
        for record in person.get('endorsements', []):
            if record.get('assessor-id') and record.get('url'):
                source_urls[record['assessor-id']].add(urldefrag(record['url'])[0])

    for directory in sorted((DATA / 'assessors').iterdir()):
        metadata_file = directory / f'{directory.name}.json'
        archive_file = DATA / 'archives/html' / f'{directory.name}.zip'
        archive_dir = DATA / 'archives/html' / directory.name
        if not metadata_file.is_file() or not (archive_file.is_file() or archive_dir.is_dir()):
            continue
        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
        configured = metadata.get('links', {}).get('processUrls', [])
        if not configured:
            continue
        pages = {}
        from scrapers.archives import ArchiveStore
        archive = ArchiveStore(archive_file if archive_file.is_file() else archive_dir)
        if archive_file.is_file():
            with ZipFile(archive_file) as file:
                names = set(file.namelist())
        else:
            names = {path.relative_to(archive_dir).as_posix() for path in archive_dir.rglob('*') if path.is_file()}
        for url in configured:
            member = next((name for name in member_candidates(directory.name, url) if name in names), None)
            if member is None:
                continue
            soup = BeautifulSoup(archive.read(member), 'html.parser')
            linked = {urldefrag(urljoin(url, str(tag['href'])))[0] for tag in soup.select('a[href]')}
            if directory.name == 'pwn2own':
                from scrapers.assessors.pwn2own import _member
                queue = [link for link in linked if urlsplit(link).path == '/blog' and 'tag=Pwn2Own' in urlsplit(link).query]
                seen = {url}
                while queue:
                    index = queue.pop()
                    if index in seen:
                        continue
                    seen.add(index)
                    body = archive.read(_member(index))
                    if body is None:
                        continue
                    more = {urldefrag(urljoin(index, str(tag['href'])))[0] for tag in BeautifulSoup(body, 'html.parser').select('a[href]')}
                    linked.update(more)
                    queue.extend(link for link in more if urlsplit(link).path == '/blog' and 'tag=Pwn2Own' in urlsplit(link).query and link not in seen)
            # Direct source URLs are already counted without an index mapping.
            indirect = (linked & source_urls[directory.name]) - set(configured)
            if indirect:
                pages[url] = sorted(indirect)
        output = directory / 'page-source-links.json'
        if pages or output.exists():
            output.write_text(json.dumps(pages, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'{directory.name}: {len(pages)}/{len(configured)} archived pages, {sum(map(len, pages.values()))} matching record links')


if __name__ == '__main__':
    main()
