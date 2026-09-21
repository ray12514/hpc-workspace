#!/usr/bin/env python3
"""Fetch pinned upstream archives and extract into a staging directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('lock')
parser.add_argument('destination')
args = parser.parse_args()
destination = Path(args.destination)
destination.mkdir(parents=True, exist_ok=True)
for asset in json.loads(Path(args.lock).read_text())['assets']:
    target = destination / asset['name']
    if target.exists():
        raise SystemExit('Refusing to replace existing asset: ' + str(target))
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / 'asset.tar.gz'
        with urllib.request.urlopen(asset['url'], timeout=120) as response, archive.open('wb') as output:
            shutil.copyfileobj(response, output)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != asset['sha256']:
            raise SystemExit('Checksum mismatch: ' + asset['name'])
        with tarfile.open(archive) as bundle:
            # Python 3.12+ extraction filter rejects paths and links escaping the destination.
            bundle.extractall(temporary, filter='data')
        shutil.move(str(Path(temporary) / asset['archive_root']), str(target))
    print('Verified and extracted ' + asset['name'] + ' ' + asset['version'])
