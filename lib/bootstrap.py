"""Bootstrap a complete release from the recommendation pinned in this checkout."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE_URL = 'https://github.com/ray12514/hpc-workspace/releases/download'


def checksum(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def matches(path, expected, size=None):
    return (path.is_file() and (size is None or path.stat().st_size == size)
            and checksum(path) == expected)


def download(url, partial):
    """Use native network configuration and retain interrupted transfers for retry."""
    curl, wget = shutil.which('curl'), shutil.which('wget')
    if curl:
        protocol = '=https' if url.startswith('https://') else '=http'
        command = [curl, '--fail', '--location', '--show-error',
                   '--progress-bar' if sys.stderr.isatty() else '--silent',
                   '--proto', protocol, '--proto-redir', protocol,
                   '--retry', '3', '--retry-delay', '2', '--connect-timeout', '30',
                   '--continue-at', '-', '--output', str(partial), url]
    elif wget:
        command = [wget, '--no-verbose', '--continue', '--tries=3', '--timeout=30',
                   '--output-document', str(partial), url]
    else:
        raise ValueError('Downloading requires curl or wget on the host.')
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        raise ValueError('Download interrupted or unavailable. Rerun ./setup to retry; '
                         'completed files and partial downloads are kept.') from None


def fetch(url, target, expected, size=None):
    if matches(target, expected, size):
        print('Verified cached ' + target.name, flush=True)
        return target
    partial = target.with_name(target.name + '.part')
    if not matches(partial, expected, size):
        print('Downloading ' + target.name, flush=True)
        download(url, partial)
    if not matches(partial, expected, size):
        if partial.exists():
            partial.unlink()
        raise ValueError('Checksum or size mismatch for ' + target.name
                         + '; installer not started. Rerun ./setup for a fresh download.')
    partial.replace(target)
    return target


def release_record(root):
    record = json.loads((root / 'releases/recommended.json').read_text())
    if (not isinstance(record, dict)
            or not isinstance(record.get('release'), str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', record['release'])
            or not isinstance(record.get('manifest_sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', record['manifest_sha256'])):
        raise ValueError('Invalid recommended release record in this checkout.')
    return record


def verify_manifest(path, release):
    manifest = json.loads(path.read_text())
    if (not isinstance(manifest, dict) or manifest.get('schema_version') != 1
            or manifest.get('layout') != 'thin-v1'
            or manifest.get('platform') != 'linux/amd64' or manifest.get('release') != release
            or not isinstance(manifest.get('artifacts'), dict)):
        raise ValueError('Unsupported or mismatched release manifest.')
    used = {path.name, 'download.lock'}
    for role in ('image', 'source', 'installer'):
        item = manifest['artifacts'].get(role)
        if (not isinstance(item, dict) or not isinstance(item.get('file'), str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,255}', item['file'])
                or item['file'].endswith('.part') or item['file'] in used
                or not isinstance(item.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])
                or type(item.get('bytes')) is not int or item['bytes'] <= 0):
            raise ValueError('Invalid ' + role + ' artifact in the release manifest.')
        used.add(item['file'])
    return manifest


def install_prefix(explicit=None):
    if explicit or os.environ.get('WS_INSTALL_ROOT'):
        return Path(explicit or os.environ['WS_INSTALL_ROOT']).expanduser().resolve()
    # Locate an installed launcher without running it. This also remembers a
    # custom prefix in a native shell where activate.sh has only updated PATH.
    launcher = shutil.which('ws')
    if launcher:
        prefix = Path(launcher).resolve().parents[1]
        if (prefix / 'activate.sh').is_file() and (prefix / 'current/installation.json').is_file():
            return prefix
    return Path.home() / '.local/share/hpc-workspace/runtime'


def setup(args, root=ROOT):
    if not args.download_only and (platform.system() != 'Linux'
                                  or platform.machine() not in ('x86_64', 'amd64')):
        raise ValueError('Install on an x86_64 Linux host, or use --download-only to prepare a transfer.')
    record = release_record(root)
    release = record['release']
    folder = Path(args.download_dir or root / 'dist/downloads').expanduser().resolve() / release
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    print('HPC workspace: recommended release ' + release, flush=True)
    with (folder / 'download.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        base = RELEASE_URL + '/v' + release + '/'
        name = 'release-' + release + '.json'
        manifest_path = fetch(base + name, folder / name, record['manifest_sha256'])
        manifest = verify_manifest(manifest_path, release)
        for role in ('image', 'source', 'installer'):
            item = manifest['artifacts'][role]
            fetch(base + item['file'], folder / item['file'], item['sha256'], item['bytes'])
        if args.download_only:
            print('Downloaded and verified all release files in ' + str(folder))
            print('Transfer this checkout including the download directory; run ./setup on the Linux host.')
            return 0
        command = [sys.executable, '-I', str(folder / manifest['artifacts']['installer']['file']),
                   str(manifest_path), '--prefix', str(install_prefix(args.prefix))]
        if args.no_shell_hook:
            command.append('--no-shell-hook')
        for path in args.shell_startup or []:
            command.extend(['--shell-startup', path])
        print('Installing the verified release...', flush=True)
        return subprocess.call(command)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-only', action='store_true', help='Prepare verified files for transfer without installing')
    parser.add_argument('--download-dir', metavar='DIRECTORY', help='Download cache parent (default: dist/downloads in this checkout)')
    parser.add_argument('--prefix', help='Installation location; otherwise reuse the active installation or the standard per-user path')
    startup = parser.add_mutually_exclusive_group()
    startup.add_argument('--shell-startup', action='append', metavar='FILE', help='Site-loaded Bash startup file; repeat for multiple files; remembered for updates')
    startup.add_argument('--no-shell-hook', action='store_true', help='Remember that startup files should not be edited')
    args = parser.parse_args(argv)
    if args.download_only and (args.prefix or args.shell_startup or args.no_shell_hook):
        parser.error('Install options cannot be used with --download-only; pass them when installing on the target host.')
    try:
        return setup(args)
    except (OSError, ValueError) as exc:
        parser.exit(2, 'workspace setup: ' + str(exc) + '\n')
    except KeyboardInterrupt:
        parser.exit(130, '\nworkspace setup: interrupted; rerun ./setup to resume.\n')
