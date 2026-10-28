#!/usr/bin/env python3
"""Download and verify the TAI archive into a new private directory."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import urllib.request

BASE = 'https://aiso-water-data.vercel.app'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New local directory outside the repository')
    parser.add_argument('--previous-manifest', type=Path, help='Optional earlier download manifest')
    args = parser.parse_args()
    key = os.getenv('AISO_API_KEY')
    if not key:
        parser.error('Set AISO_API_KEY in your environment; do not include the key in commands or logs.')
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; choose a new path to preserve earlier downloads.')
    output.mkdir(parents=True)
    headers = {'X-API-Key': key}
    def request(url):
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)
    with request(BASE + '/files') as response:
        listing = json.load(response)
    matches = [x for x in listing['files'] if x['path'] == 'tai/tai_all.tar']
    if len(matches) != 1:
        raise ValueError('Expected exactly one TAI archive in the organiser listing')
    item = matches[0]
    archive = output / 'tai_all.tar'
    partial = output / 'tai_all.tar.partial'
    with request(BASE + '/files/tai/tai_all.tar') as response, partial.open('wb') as destination:
        shutil.copyfileobj(response, destination)
    if partial.stat().st_size != item['size_bytes']:
        raise ValueError('Download size mismatch; incomplete file retained as .partial')
    sha = digest(partial)
    official = item.get('sha256')
    if official and sha.lower() != official.lower():
        raise ValueError('Official SHA-256 mismatch; incomplete file retained as .partial')
    partial.rename(archive)
    extracted = output / 'extracted'
    extracted.mkdir()
    files = []
    with tarfile.open(archive) as tar:
        for member in tar:
            target = (extracted / member.name).resolve()
            if not target.is_relative_to(extracted) or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive entry')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None or target.exists():
                raise ValueError('Missing or duplicate archive entry')
            with source, target.open('xb') as dest:
                shutil.copyfileobj(source, dest)
            if target.stat().st_size != member.size:
                raise ValueError('Extracted file size mismatch')
            if target.suffix == '.gz':
                with gzip.open(target, 'rb') as gz:
                    while gz.read(1024 * 1024):
                        pass
            files.append({'path': str(target.relative_to(extracted)), 'bytes': member.size, 'sha256': digest(target)})
    previous = None
    if args.previous_manifest:
        old = json.loads(args.previous_manifest.read_text(encoding='utf-8'))
        previous = next((x.get('sha256') for x in old.get('verified_downloads', []) if x.get('path') == 'tai/tai_all.tar'), None)
    manifest = {'downloaded_at_utc': datetime.now(timezone.utc).isoformat(), 'source': BASE + '/files/tai/tai_all.tar', 'archive_bytes': archive.stat().st_size, 'archive_sha256': sha, 'official_sha256': official, 'previous_archive_sha256': previous, 'matches_previous': sha == previous if previous else None, 'extracted_files': files}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Verified {len(files)} extracted files; archive SHA-256: {sha}')
    if previous:
        print(f'Matches earlier archive: {sha == previous}; differences require investigation.')


if __name__ == '__main__':
    main()
