"""Private, shared-filesystem locations for node-local managed tmux keepers."""
import datetime
import hashlib
import json
from pathlib import Path
import socket

import integration
import releases


def host_key(hostname):
    return hashlib.sha256(hostname.encode()).hexdigest()[:16]


def boot_id():
    try:
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip() or None
    except OSError:
        return None


def keeper_running(record):
    """Only call for this host; a PID on another node has no local meaning."""
    if record.get('boot_id') and record['boot_id'] != boot_id():
        return False
    return bool(record.get('identity') and
                integration.process_identity(record.get('pid')) == record['identity'])


def save(path, keeper, site, project, release):
    record = dict(keeper)
    record.update(schema_version=1, hostname=socket.gethostname(), site=site,
                  project=str(project), release=release, boot_id=boot_id(),
                  recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    releases.atomic_text(path, json.dumps(record, indent=2) + '\n')
    return record


def read_object(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def locations(state):
    """Read records without contacting nodes, starting containers, or changing state."""
    hostname = socket.gethostname()
    rows, warnings = [], []
    for path in sorted((state / 'session-hosts').glob('*/*.json')):
        try:
            record = read_object(path)
            recorded_host = record.get('hostname')
            if not recorded_host:
                # Older releases used the same host hash for their mount recipe.
                recipe = state / 'integration' / (path.parent.name + '.json')
                if recipe.is_file():
                    recorded_host = read_object(recipe).get('hostname')
                elif path.parent.name == host_key(hostname):
                    recorded_host = hostname
            if recorded_host is not None and (not isinstance(recorded_host, str) or
                    host_key(recorded_host) != path.parent.name):
                raise ValueError('Hostname does not match the record directory')
            release = record.get('release')
            ready = path.with_suffix('.ready')
            if not release and ready.is_file():
                release = read_object(ready).get('release')
            status = 'recorded' if recorded_host else 'unknown-node'
            if recorded_host == hostname:
                if keeper_running(record):
                    status = 'local-ready' if ready.is_file() else 'local-starting'
                else:
                    status = 'local-ended'
            # Select metadata only; do not copy arbitrary JSON into output.
            rows.append({'hostname': recorded_host, 'session': record.get('session', path.stem),
                         'site': record.get('site'), 'project': record.get('project'),
                         'release': release, 'image': record.get('image'),
                         'recorded_at': record.get('recorded_at'), 'status': status,
                         'record': str(path)})
        except (OSError, ValueError, TypeError) as exc:
            warnings.append('Cannot read session record {}: {}'.format(path, exc))
    return {'schema_version': 1, 'hostname': hostname, 'state_dir': str(state),
            'sessions': rows, 'warnings': warnings}


def display(value):
    """Keep paths and node names containing control characters on one safe line."""
    if value is None:
        return '(not recorded)'
    return json.dumps(str(value), ensure_ascii=True)[1:-1]
