#!/usr/bin/env python3
"""Install a transferred thin release atomically; also usable as a standalone installer."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import tarfile
import tempfile


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def default_prefix():
    return Path(os.environ.get('WS_INSTALL_ROOT', str(Path.home() / '.local/share/hpc-workspace/runtime'))).expanduser().resolve()


def atomic_text(path, text, mode=0o600):
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def point(path, target):
    temporary = path.with_name('.' + path.name + '-' + str(os.getpid()))
    try:
        temporary.symlink_to(target)
        temporary.replace(path)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def shell_hook_text(path, activation):
    start, end = '# >>> hpc-workspace managed PATH >>>', '# <<< hpc-workspace managed PATH <<<'
    source = shlex.quote(str(activation))
    block = start + '\nif [ -r ' + source + ' ]; then\n    . ' + source + '\nfi\n' + end
    contents = path.read_text() if path.exists() else ''
    if start in contents or end in contents:
        pattern = re.escape(start) + r'.*?' + re.escape(end)
        if contents.count(start) != 1 or contents.count(end) != 1 or not re.search(pattern, contents, re.S):
            raise ValueError('Incomplete or duplicate workspace PATH block in ' + str(path))
        return re.sub(pattern, lambda _: block, contents, flags=re.S)
    return contents + ('' if not contents or contents.endswith('\n') else '\n') + '\n' + block + '\n'


def configure_shell(prefix, shell_hook=True, startup_files=None):
    """Remember a local startup-file choice; default to normal Bash startup."""
    home = Path.home()
    settings = prefix / 'shell-startup.json'
    if not shell_hook:
        if startup_files:
            raise ValueError('--shell-startup cannot be combined with --no-shell-hook')
        policy = {'schema_version': 1, 'mode': 'none', 'files': []}
    elif startup_files is not None:
        policy = {'schema_version': 1, 'mode': 'custom',
                  'files': [os.path.abspath(str(Path(p).expanduser())) for p in startup_files]}
    elif settings.exists():
        policy = json.loads(settings.read_text())
    else:
        policy = {'schema_version': 1, 'mode': 'auto', 'files': []}
    if (not isinstance(policy, dict) or policy.get('schema_version') != 1
            or policy.get('mode') not in ('none', 'auto', 'custom')
            or not isinstance(policy.get('files'), list)
            or any(not isinstance(p, str) or not Path(p).is_absolute() for p in policy['files'])
            or (policy['mode'] == 'custom' and not policy['files'])):
        raise ValueError('Invalid local shell startup configuration: ' + str(settings))
    paths = []
    if policy['mode'] == 'custom':
        paths = [Path(p) for p in policy['files']]
    elif policy['mode'] == 'auto':
        profiles = [home / name for name in ('.bash_profile', '.bash_login', '.profile')]
        # Bash reads only its first readable login profile; do not hide another
        # existing profile by creating a higher-priority one.
        login = next((p for p in profiles if p.is_file() and os.access(str(p), os.R_OK)), profiles[0])
        paths = [home / '.bashrc', login]
    changes = []
    for path in paths:
        if path.is_dir():
            raise ValueError('Choose a startup file, not a directory: ' + str(path))
        contents = shell_hook_text(path, prefix / 'activate.sh')
        destination = path.resolve() if path.is_symlink() else path
        if all(destination != prior[0] for prior in changes):
            changes.append((destination, contents))
    # Validate both blocks before replacing either personal file. Follow an
    # existing dotfile symlink, preserving the symlink and the target's mode.
    for destination, contents in changes:
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(destination, contents, destination.stat().st_mode & 0o777 if destination.exists() else 0o644)
    atomic_text(settings, json.dumps(policy, indent=2) + '\n')


def unpack(source, destination):
    destination.mkdir(mode=0o700)
    links, seen, total = [], set(), 0
    with tarfile.open(source, 'r:gz') as archive:
        for count, member in enumerate(archive):
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != 'hpc-workspace' or '..' in parts or member.name.startswith('/'):
                raise ValueError('Source archive contains an unsafe path')
            relative = Path(*parts[1:])
            if str(relative) == '.':
                continue
            if relative in seen or count > 50000:
                raise ValueError('Source archive has duplicate paths or too many entries')
            seen.add(relative)
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                total += member.size
                if total > 256 * 1024 * 1024:
                    raise ValueError('Source archive exceeds the installation limit')
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as src, target.open('xb') as out:
                    shutil.copyfileobj(src, out)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym():
                if PurePosixPath(member.linkname).is_absolute():
                    raise ValueError('Source archive contains an unsafe link')
                links.append((target, member.linkname))
            else:
                raise ValueError('Source archive contains an unsupported entry')
    # Create links after all regular files, so extraction never follows a link.
    for target, link in links:
        target.parent.mkdir(parents=True, exist_ok=True)
        resolved = (target.parent / link).resolve()
        try:
            resolved.relative_to(destination.resolve())
        except ValueError:
            raise ValueError('Source archive link escapes its directory')
        target.symlink_to(link)
    for target, _ in links:
        try:
            target.resolve().relative_to(destination.resolve())
        except (ValueError, RuntimeError):
            raise ValueError('Source archive contains an unsafe link chain')
    if not (destination / 'bin/ws').is_file() or not (destination / 'lib/workspace.py').is_file():
        raise ValueError('Source archive is missing the workspace launcher')


def verify_installed(folder):
    record = json.loads((folder / 'installation.json').read_text())
    if digest(folder / 'image.sif') != record['image_sha256']:
        raise ValueError('Installed image checksum mismatch; selection unchanged')
    return record


def install(manifest_path, prefix=None, shell_hook=True, startup_files=None):
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('This release installer targets x86_64 Linux')
    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text())
    release = manifest.get('release', '')
    if manifest.get('schema_version') != 1 or manifest.get('layout') != 'thin-v1' or manifest.get('platform') != 'linux/amd64':
        raise ValueError('Unsupported thin release manifest')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', release):
        raise ValueError('Invalid release name')
    artifacts = {}
    for role in ('image', 'source'):
        item = manifest.get('artifacts', {}).get(role, {})
        name = item.get('file', '')
        if not name or Path(name).name != name or name in ('.', '..') or not re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', '')):
            raise ValueError('Invalid ' + role + ' artifact record')
        source = manifest_path.parent / name
        if digest(source) != item['sha256']:
            raise ValueError(role + ' checksum mismatch; selection unchanged')
        artifacts[role] = source
    prefix = Path(prefix or default_prefix()).expanduser().resolve()
    prefix.mkdir(parents=True, exist_ok=True, mode=0o700)
    (prefix / 'releases').mkdir(exist_ok=True)
    fd = os.open(str(prefix / 'install.lock'), os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        target = prefix / 'releases' / release
        record = {'release': release, 'image_sha256': manifest['artifacts']['image']['sha256'],
                  'source_sha256': manifest['artifacts']['source']['sha256'], 'layout': 'thin-v1'}
        if target.exists():
            if verify_installed(target) != record:
                raise ValueError('Release name already contains different content')
        else:
            stage = Path(tempfile.mkdtemp(prefix='.install-', dir=str(prefix / 'releases')))
            try:
                shutil.copyfile(artifacts['image'], stage / 'image.sif')
                if digest(stage / 'image.sif') != record['image_sha256']:
                    raise ValueError('Image changed while copying; selection unchanged')
                # Snapshot source before extraction, avoiding a transfer changing it midway.
                source_copy = stage / 'source.tar.gz'
                shutil.copyfile(artifacts['source'], source_copy)
                if digest(source_copy) != record['source_sha256']:
                    raise ValueError('Source changed while copying; selection unchanged')
                unpack(source_copy, stage / 'source')
                source_copy.unlink()
                (stage / 'image.sif.json').write_text(json.dumps({
                    'schema_version': 1, 'layout': 'thin-v1', 'platform': 'linux/amd64',
                    'release': release, 'sha256': record['image_sha256']}) + '\n')
                (stage / 'installation.json').write_text(json.dumps(record) + '\n')
                stage.rename(target)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        (prefix / 'bin').mkdir(exist_ok=True)
        launcher = '#!/bin/sh\nexport WS_INSTALL_ROOT=' + shlex.quote(str(prefix)) + '\nexec python3 "$WS_INSTALL_ROOT/current/source/bin/ws" "$@"\n'
        atomic_text(prefix / 'bin/ws', launcher, 0o755)
        activation = 'case ":${PATH}:" in\n  *:' + shlex.quote(str(prefix / 'bin')) + ':*) ;;\n  *) export PATH=' + shlex.quote(str(prefix / 'bin')) + ':"$PATH" ;;\nesac\n'
        atomic_text(prefix / 'activate.sh', activation, 0o644)
        configure_shell(prefix, shell_hook, startup_files)
        current = prefix / 'current'
        if current.is_symlink() and current.resolve() != target:
            point(prefix / 'previous', os.readlink(str(current)))
        point(current, 'releases/' + release)
    return {'release': release, 'prefix': str(prefix), 'launcher': str(prefix / 'bin/ws')}


def rollback(prefix=None):
    prefix = Path(prefix or default_prefix()).resolve()
    with (prefix / 'install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = prefix / 'previous'
        if not previous.is_symlink():
            raise ValueError('No previous installed release')
        record = verify_installed(previous.resolve())
        old = os.readlink(str(prefix / 'current'))
        target = os.readlink(str(previous))
        point(prefix / 'current', target)
        point(previous, old)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('--prefix')
    startup = parser.add_mutually_exclusive_group()
    startup.add_argument('--no-shell-hook', action='store_true', help='Remember that startup files should not be edited')
    startup.add_argument('--shell-startup', action='append', metavar='FILE', help='Use this site-loaded Bash startup file; repeat for multiple files; remembered for updates')
    args = parser.parse_args()
    try:
        result = install(args.manifest, args.prefix, not args.no_shell_hook, args.shell_startup)
        print('Installed {release}. Run {launcher} enter, or open a new Bash session and run ws enter.'.format(**result))
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        parser.exit(2, 'workspace install: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
