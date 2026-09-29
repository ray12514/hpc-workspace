"""Select and control an existing managed workspace without creating a keeper."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

import integration
import session_records


@contextmanager
def session_lock(path):
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another startup or stop is active for this workspace. '
                             'No additional keeper was started. Local log: ' +
                             str(path.with_suffix('.log')))
        yield


def select(state, name=None, project=None, stopping=False, site='local'):
    if stopping and not (name or project):
        raise ValueError('Choose the workspace to stop with --session NAME or --project PATH; '
                         'list choices with ws sessions.')
    report = session_records.locations(state)
    rows = report['sessions']
    for row in rows:
        row['site'] = row['site'] or site
    if name:
        rows = [row for row in rows if row['session'] == name]
    if project:
        project = str(Path(project).expanduser().resolve())
        rows = [row for row in rows if row['project'] == project or
                (name and not row['project'] and row['release'] and
                 integration.session_name(row['site'] or 'local', project, row['release']) == name)]
    local = [row for row in rows if row['hostname'] == report['hostname']]
    running = [row for row in local if row['status'] != 'local-ended']
    choices = running or local
    if not choices:
        remote = sorted({row['hostname'] for row in rows if row['hostname']})
        detail = (' Recorded on: ' + ', '.join(session_records.display(host) for host in remote)
                  if remote else '')
        raise ValueError('No matching managed workspace on this node.' + detail +
                         ' Use ws sessions and reconnect to the recorded node. No workspace was created.')
    if len(choices) != 1:
        names = ', '.join(session_records.display(row['session']) for row in choices)
        raise ValueError('Multiple managed workspaces match: ' + names +
                         '. Choose one with --session NAME.')
    row = choices[0]
    if project and not row['project']:
        row['project'] = project
    return row


# Sent to the original image's private Python, so controls also work with older
# thin images. No new image, daemon, shell interpolation or environment dump.
CONTROL = '''
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/workspace-tools/lib')
from integration import process_identity

name, operation, pid, identity, detach = sys.argv[1:]
print('Entered workspace image; checking existing tmux server ' + name, flush=True)
if process_identity(int(pid)) != identity:
    raise SystemExit('Recorded keeper ended or changed during entry; no control action sent.')
os.environ['WS_SESSION_STATE'] = str(Path(os.environ['WS_STATE_HOME']) / 'tmux' / os.uname().nodename / name)
base = ['/workspace-tools/bin/tmux', '-N', '-L', name, '-f', '/workspace-tools/config/tmux/tmux.conf']
try:
    result = subprocess.run(base + ['has-session', '-t', '=' + name],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
    if result.returncode:
        raise SystemExit('Recorded tmux session is unavailable. No replacement was created.')
    if operation == 'check':
        print('Existing tmux session responds: ' + name, flush=True)
    elif operation == 'stop':
        if process_identity(int(pid)) != identity:
            raise SystemExit('Recorded keeper changed; stop cancelled.')
        subprocess.run(base + ['kill-server'], check=True, timeout=10)
        print('Stop delivered to selected workspace tmux server: ' + name, flush=True)
    else:
        print('Attaching to existing workspace: ' + name, flush=True)
        command = base + ['attach-session', '-t', '=' + name]
        if detach == 'detach-others':
            command.append('-d')
        os.execvpe(command[0], command, os.environ)
except subprocess.TimeoutExpired:
    raise SystemExit('Existing tmux server did not respond within 10 seconds. No new workspace was created.')
'''


def command(row, record, operation, detach_others=False):
    if not row['project'] or not row['release']:
        raise ValueError('Legacy record lacks project/release metadata. Supply the original --project PATH '
                         'with --session NAME, or inspect its ws sessions record.')
    expected = integration.session_name(row['site'] or 'local', row['project'], row['release'])
    if row['session'] != expected or Path(row['record']).stem != expected:
        raise ValueError('Session identity does not match its recorded project/site/release; no action sent.')
    if not isinstance(record.get('pid'), int) or record['pid'] <= 1 or not record.get('identity'):
        raise ValueError('Session has no usable keeper identity; no action sent.')
    return ['/workspace-tools/libexec/python3', '-I', '-c', CONTROL, row['session'], operation,
            str(record['pid']), str(record['identity']), 'detach-others' if detach_others else 'keep-clients']
