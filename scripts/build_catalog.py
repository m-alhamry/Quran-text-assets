#!/usr/bin/env python3
"""Prepare immutable QuranEnc packages. Standard library + curl; never edits text."""
import argparse
import csv
import gzip
import hashlib
import html
import json
import pathlib
import re
import subprocess
import time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
COUNTS = json.loads((ROOT / 'scripts/verse_counts.json').read_text())
EXPECTED = {(s, a) for s, n in enumerate(COUNTS, 1) for a in range(1, n + 1)}
POLICY = 'https://quranenc.com/en/home/api/'
HUB = 'https://github.com/IslamHouse-API/multilingual-quran-hadith-islamic-content-database-api-hub'
BASE = 'https://raw.githubusercontent.com/m-alhamry/Quran-text-assets/main/'
CDN = 'https://cdn.jsdelivr.net/gh/m-alhamry/Quran-text-assets@main/'


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def validate_rows(rows):
    result = {}
    seen = set()
    for s, a, text, notes in rows:
        key = (int(s), int(a))
        if key not in EXPECTED or key in seen:
            raise ValueError(f'Unexpected/duplicate verse: {key}')
        if not isinstance(text, str) or not isinstance(notes, str):
            raise ValueError(f'Invalid text or footnotes: {key}')
        plain = html.unescape(re.sub('<[^>]*>', '', text)).strip()
        if not plain or plain.lower() in {'-', '--', '.', '...', '…', 'null', 'undefined', 'n/a'}:
            raise ValueError(f'Missing/placeholder text: {key}')
        seen.add(key)
        result.setdefault(str(key[0]), {})[str(key[1])] = {'text': text, 'footnotes': notes}
    if seen != EXPECTED:
        raise ValueError(f'Missing {len(EXPECTED - seen)} verses')
    return result


def fetch(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.part')
    subprocess.run(['curl', '-fL', '-sS', '--retry', '2', '--retry-delay', '3',
                    '--max-time', '90', '--max-filesize', '67108864', url,
                    '-o', str(temporary)], check=True)
    if not temporary.stat().st_size:
        temporary.unlink()
        raise ValueError(f'Empty response: {url}')
    temporary.replace(destination)


def load_rows(entry, cache, refresh=False):
    key = entry['sourceKey']
    if entry['format'] == 'csv':
        path = cache / f'{key}.csv'
        if refresh or not path.exists():
            fetch(f'https://quranenc.com/en/home/d/csv/{key}', path)
        rows = list(csv.reader(path.read_text(encoding='utf-8-sig').splitlines(keepends=True)))
        header = next(i for i, row in enumerate(rows) if row[:3] == ['id', 'sura', 'aya'])
        metadata = '\n'.join(' '.join(row) for row in rows[:header])
        if f'v{entry["version"]}-' not in metadata:
            raise ValueError(f'Source version changed: {key}; review editions.json first')
        return [(r[1], r[2], r[3], r[4]) for r in rows[header + 1:] if r and any(r)], metadata
    rows = []
    for chapter in range(1, 115):
        path = cache / f'{key}-sura{chapter}.json'
        if refresh or not path.exists():
            fetch(f'https://quranenc.com/api/v1/translation/sura/{key}/{chapter}', path)
            time.sleep(.15)
        data = json.loads(path.read_text())['result']
        if len(data) != COUNTS[chapter - 1]:
            raise ValueError(f'Incomplete chapter: {key}/{chapter}')
        for r in data:
            if int(r['sura']) != chapter:
                raise ValueError('Wrong chapter')
            rows.append((r['sura'], r['aya'], r['translation'], r.get('footnotes') or ''))
    return rows, f'QuranEnc.com; {entry["sourceUrl"]}; version {entry["version"]}'


def verify_source_versions(entries, cache):
    path = cache / 'upstream-catalogue.html'
    fetch('https://quranenc.com/en/home', path)
    body = path.read_text()
    for entry in entries:
        # Every card's version precedes its unique browse link. Fail closed
        # when their markup changes; never stamp new content with an old version.
        cards = body.split('class="tab_card ')
        matches = [c for c in cards if f'/browse/{entry["sourceKey"]}"' in c]
        versions = [re.search(r'\bV([0-9]+(?:\.[0-9]+)+)', c) for c in matches]
        if not versions or not all(v and v[1] == entry['version'] for v in versions):
            raise ValueError(f'Upstream metadata changed or unavailable: {entry["sourceKey"]}; review before publishing')


def build(cache, refresh=False, verify_versions=True):
    entries = json.loads((ROOT / 'editions.json').read_text())
    catalogue_path = ROOT / 'api/v1/catalog.json'
    old = json.loads(catalogue_path.read_text()) if catalogue_path.exists() else {}
    old_versions = {e['sourceKey']: e['version'] for e in old.get('editions', [])}
    if not refresh and any(e['sourceKey'] in old_versions and
                           old_versions[e['sourceKey']] != e['version'] for e in entries):
        raise ValueError('A version changed: use --refresh, never relabel cached source data')
    if verify_versions:
        verify_source_versions(entries, cache)
    output = []
    for entry in entries:
        source_rows, transcript = load_rows(entry, cache, refresh)
        verses = validate_rows(source_rows)
        metadata = {k: v for k, v in entry.items() if k != 'format'}
        metadata.update(source='QuranEnc.com', policyUrl=POLICY, permissionUrl=HUB,
                        transcript=transcript)
        raw = encode({'schemaVersion': 1, 'edition': metadata, 'verses': verses})
        packed = gzip.compress(raw, mtime=0)
        digest = hashlib.sha256(packed).hexdigest()
        relative = f'data/{entry["sourceKey"]}/{entry["version"]}-{digest[:16]}.json.gz'
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != packed:
            raise ValueError('Immutable package collision')
        target.write_bytes(packed)
        output.append(dict(metadata, urls=[BASE + relative, CDN + relative], sha256=digest,
                           sizeBytes=len(packed), uncompressedBytes=len(raw)))
        print(entry['sourceKey'], len(packed), 'bytes; 6236 verses verified', flush=True)
    if old.get('editions') == output:
        print('Catalogue unchanged')
        return
    catalogue = dict(schemaVersion=1, readerVersion=1, revision=old.get('revision', 0) + 1,
                     publishedAt=datetime.now(timezone.utc).isoformat(), editions=output)
    catalogue_path.parent.mkdir(parents=True, exist_ok=True)
    catalogue_path.write_bytes(encode(catalogue))


def validate_repository():
    catalog = json.loads((ROOT / 'api/v1/catalog.json').read_text())
    assert catalog['schemaVersion'] == catalog['readerVersion'] == 1
    ids = set()
    aliases = set()
    for e in catalog['editions']:
        assert re.fullmatch(r'[a-z]{2}_qe_[a-z0-9_]+', e['id']) and e['id'] not in ids
        ids.add(e['id'])
        for alias in e['legacyIds']:
            assert alias not in aliases
            aliases.add(alias)
        assert e['urls'][0].startswith(BASE)
        path = ROOT / e['urls'][0][len(BASE):]
        packed = path.read_bytes()
        assert len(packed) == e['sizeBytes'] and hashlib.sha256(packed).hexdigest() == e['sha256']
        raw = gzip.decompress(packed)
        assert len(raw) == e['uncompressedBytes']
        payload = json.loads(raw)
        assert payload['schemaVersion'] == 1
        assert payload['edition'] == {k: v for k, v in e.items() if k not in {'urls', 'sha256', 'sizeBytes', 'uncompressedBytes'}}
        validate_rows((s, a, v['text'], v['footnotes']) for s, verses in payload['verses'].items() for a, v in verses.items())
    print(f'Validated {len(ids)} editions / {len(ids) * 6236:,} verses')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'validate', 'check-updates'])
    parser.add_argument('--cache', type=pathlib.Path, default=ROOT / '.source-cache')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if args.command == 'validate':
        validate_repository()
    elif args.command == 'check-updates':
        verify_source_versions(json.loads((ROOT / 'editions.json').read_text()), args.cache)
        print('Configured source versions are current')
    else:
        build(args.cache, refresh=args.refresh)
        validate_repository()
