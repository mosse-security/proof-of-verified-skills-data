"""Backfill verified event locations; safe to rerun after interruption.

Run from the repository root with --apply to write. Without it, only report.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scrapers.locations import endorsement_location
from scrapers.schema import AssessorMetadata, validate_endorsement_record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write changes; default is a dry run')
    parser.add_argument('--refresh-def-con', action='store_true', help='Correct existing DEF CON locations to United States')
    args = parser.parse_args()
    metadata = {}
    for folder in Path('data/assessors').iterdir():
        path = folder / f'{folder.name}.json'
        if path.is_file():
            metadata[folder.name] = AssessorMetadata.from_file(path)
    paths = list(Path('data/individuals').glob('*.json'))
    paths += list(Path('data/assessors').glob('*/individuals/*.json'))
    counts: Counter[str] = Counter()
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    for index, path in enumerate(paths, 1):
        document = json.loads(path.read_text(encoding='utf-8'))
        changed = False
        for record in document.get('endorsements', []):
            assessor = metadata.get(record.get('assessor-id'))
            previous = record.get('location')
            refresh_def_con = args.refresh_def_con and record.get('assessor-id') == 'def-con'
            if not refresh_def_con and isinstance(previous, str) and previous.strip().casefold() != 'unknown' and previous.strip():
                continue
            assessor_id = record.get('assessor-id', '')
            inferred = endorsement_location(assessor_id, record.get('url', ''), record.get('subtitle'), record.get('year', 0), assessor.countries if assessor else ()) if isinstance(assessor_id, str) else None
            location = inferred or 'Unknown'
            if previous == location:
                if location == 'Unknown':
                    counts['unclassified'] += 1
                continue
            record['location'] = location
            validate_endorsement_record(record, source=str(path), assessor=assessor)
            counts[location] += 1
            changed = True
        if changed:
            counts['files'] += 1
            if args.apply:
                if 'last-updated' in document:
                    document['last-updated'] = timestamp
                contents = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
                temp_name = ''
                try:
                    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent, delete=False) as temp:
                        temp_name = temp.name
                        temp.write(contents)
                    os.replace(temp_name, path)
                finally:
                    if temp_name and os.path.exists(temp_name):
                        os.unlink(temp_name)
        if index % 1000 == 0:
            print(f'Checked {index}/{len(paths)} files; {counts["files"]} need updates.', flush=True)
    print(('Applied' if args.apply else 'Dry run') + ': ' + json.dumps(counts, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
