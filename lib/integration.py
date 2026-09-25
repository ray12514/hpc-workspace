"""Automatic host filesystem/environment integration for the thin image layout."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import tempfile
import runtime_setup

LAYOUT = 'thin-v1'
RESERVED = {'nix', 'workspace-tools', 'workspace-state', 'workspace-bootstrap'}
KERNEL = {'dev', 'proc', 'sys'}
READ_ONLY = {'usr', 'bin', 'sbin', 'lib', 'lib32', 'lib64', 'libx32', 'etc', 'opt', 'boot'}


def descriptor(image):
    path = Path(str(image) + '.json')
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if data.get('schema_version') != 1 or data.get('layout') != LAYOUT:
        raise ValueError('Unsupported workspace image descriptor: ' + str(path))
    if data.get('platform') != 'linux/amd64':
        raise ValueError('Thin image requires a linux/amd64 descriptor')
    return {'layout': LAYOUT, 'release': data['release']}


def host_mounts(root=Path('/')):
    """One coherent host userspace, preserving the image's private tool paths."""
    root = Path(root)
    mounts = []
    for name in RESERVED:
        path = root / name
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError('Host path conflicts with the thin image: /' + name)
    for path in sorted(root.iterdir()):
        if path.name.startswith('.') or path.name in RESERVED | KERNEL:
            continue
        if not path.is_dir() or not os.access(str(path), os.X_OK):
            continue
        mounts.append({'source': str(path.resolve()), 'destination': '/' + path.name,
                       'mode': 'ro' if path.name in READ_ONLY else 'rw'})
    return mounts


def validate_extra(item):
    if not isinstance(item, dict) or 'source' not in item or set(item) - {'source', 'destination', 'mode'}:
        raise ValueError('Invalid profile bind')
    destination = os.path.normpath(item.get('destination', item['source']))
    if not destination.startswith('/'):
        raise ValueError('Bind destination must be absolute')
    top = destination.split('/')[1] if destination != '/' else ''
    if not top or top in RESERVED | KERNEL | READ_ONLY:
        raise ValueError('Profile bind would replace a protected integration path: ' + destination)
    return destination


def plan(image, project, state, data, args, bind_spec, environment_file=None, create_state=False):
    if platform.system() != 'Linux':
        raise ValueError('The thin host integration must be planned on Linux')
    if platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('This thin release targets x86_64 Linux')
    if args.host_jobs:
        raise ValueError('The thin shell uses ordinary site commands directly; --host-jobs is for the core image')
    mounts = host_mounts()
    for item in data.get('binds', []):
        mounts.append(dict(item, destination=validate_extra(item)))
    for source in (Path.home(), project, Path(args.work).expanduser().resolve() if args.work else None):
        if source is not None:
            if source == Path('/') or source.parts[1] in RESERVED | KERNEL:
                raise ValueError('Workspace directory would shadow a reserved image path: ' + str(source))
            mounts.append({'source': str(source), 'destination': str(source), 'mode': 'rw'})
    # These paths are the only image-specific mounts; root and host OS paths are
    # never overmounted by arbitrary profile values.
    command = runtime_setup.command() + ['exec', '--cleanenv', '--no-eval',
               '--no-mount', 'home,cwd,hostfs,bind-paths', '--pwd', str(project)]
    for item in mounts:
        command += ['--bind', bind_spec(item['source'], item['destination'], item.get('mode', 'ro'))]
    if any(c in str(state) for c in (',', ':', '\n', '\r')):
        raise ValueError('Unsupported character in state path')
    command += ['--bind', str(state) + ':/workspace-state:rw']
    if environment_file:
        command += ['--bind', bind_spec(Path(environment_file).parent, '/workspace-bootstrap', 'ro')]
    if args.gpu != 'none':
        command.append('--nv' if args.gpu == 'cuda' else '--rocm')
    requested = list(args.command)
    if requested[:1] == ['--']:
        requested.pop(0)
    command += [image['path'], '/workspace-tools/thin-entry'] + requested
    # Restore all host values from a private JSON snapshot in thin-entry. No
    # credentials in argv, no shell interpolation, no permanent environment dump.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(('APPTAINER', 'SINGULARITY'))}
    if create_state:
        record = {'schema_version': 1, 'layout': LAYOUT, 'hostname': socket.gethostname(),
                  'image': image['path'], 'mounts': mounts}
        folder = state / 'integration'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16] + '.json'
        destination = folder / name
        contents = json.dumps(record, indent=2) + '\n'
        if not destination.exists() or destination.read_text() != contents:
            fd, temporary = tempfile.mkstemp(dir=str(folder), prefix='.integration-')
            try:
                with os.fdopen(fd, 'w') as stream:
                    stream.write(contents)
                os.replace(temporary, str(destination))
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    return command, environment


@contextmanager
def snapshot(args, state):
    # Private ephemeral data; the cached integration recipe contains no values.
    with tempfile.TemporaryDirectory(prefix='workspace-start-') as directory:
        path = Path(directory) / 'environment.json'
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump({'schema_version': 1, 'environment': dict(os.environ),
                       'state': str(state), 'site': args.site, 'hostname': socket.gethostname(),
                       'snapshot_source': str(path), 'gpu': getattr(args, 'gpu', 'none'),
                       'project': str(Path(getattr(args, 'project', os.getcwd())).resolve())}, stream)
        yield path


def session_name(site, project, release):
    key = hashlib.sha256((site + "\0" + str(project)).encode()).hexdigest()[:12]
    return 'ws-' + key + '-' + hashlib.sha256(release.encode()).hexdigest()[:8]


def process_identity(pid):
    try:
        fields = Path('/proc/{}/stat'.format(int(pid))).read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except (OSError, ValueError, TypeError, IndexError):
        return None
