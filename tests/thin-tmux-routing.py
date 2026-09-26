"""Exercise implicit tmux clients and layout saving inside the real managed server."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time


def call(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=15, **kwargs)


def probe(destination, other_socket):
    result = {}
    for label, command in (
        ('current', ['tmux', 'display-message', '-p', '#{socket_path}']),
        ('explicit', ['tmux', '-S', other_socket, 'display-message', '-p', '#{socket_path}']),
        ('save', [os.environ['WS_ROOT'] + '/share/tmux-resurrect/scripts/save.sh', 'quiet']),
    ):
        completed = call(command)
        result[label] = {'status': completed.returncode, 'stdout': completed.stdout.strip(),
                         'stderr': completed.stderr.strip()}
    Path(destination).write_text(json.dumps(result))


def exercise():
    environment = dict(os.environ)
    environment.pop('TMUX', None)
    environment.pop('TMUX_PANE', None)
    default = ['tmux', '-f', '/dev/null']
    with tempfile.TemporaryDirectory(prefix='tmux-routing-') as temporary:
        root = Path(temporary)
        ready = root / 'ready.json'
        report = root / 'probe.json'
        keeper = None
        managed = None
        try:
            # A separate default server makes incorrect routing visible even
            # when it silently succeeds instead of reporting a missing socket.
            call(default + ['new-session', '-d', '-s', 'routing-decoy', 'sleep', '120'],
                 env=environment, check=True)
            other_socket = call(default + ['display-message', '-p', '#{socket_path}'],
                                env=environment, check=True).stdout.strip()
            keeper = subprocess.Popen(['/workspace-tools/thin-session', '--serve', str(ready)],
                                      env=environment)
            deadline = time.monotonic() + 20
            while not ready.exists() and time.monotonic() < deadline:
                assert keeper.poll() is None, 'Managed keeper exited before becoming ready'
                time.sleep(.05)
            name = json.loads(ready.read_text())['session']
            managed = ['tmux', '-L', name]
            expected = call(managed + ['display-message', '-p', '#{socket_path}'],
                            env=environment, check=True).stdout.strip()
            command = shlex.join([sys.executable, '-I', str(Path(__file__).resolve()),
                                  '--probe', str(report), other_socket])
            call(managed + ['send-keys', '-t', name + ':workspace', '-l', command],
                 env=environment, check=True)
            call(managed + ['send-keys', '-t', name + ':workspace', 'Enter'],
                 env=environment, check=True)
            deadline = time.monotonic() + 20
            while not report.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            result = json.loads(report.read_text())
            assert result['current']['status'] == 0 and result['current']['stdout'] == expected, (
                'Implicit client left its managed server', expected, result)
            assert result['explicit']['stdout'] == other_socket, result
            assert result['save']['status'] == 0, result
            bindings = call(managed + ['list-keys', '-T', 'prefix'],
                            env=environment, check=True).stdout
            assert any('C-s' in line and 'tmux-resurrect/scripts/save.sh' in line
                       for line in bindings.splitlines()), bindings
            snapshots = Path(environment['WS_STATE_HOME']) / 'tmux' / os.uname().nodename / name
            contents = (snapshots / 'last').read_text()
            assert name in contents and 'routing-decoy' not in contents, contents
            assert all(window in contents for window in ('workspace', 'editor', 'agents')), contents
            print('PASS: implicit tmux targets its managed server; explicit selection works; '
                  'save binding and snapshot belong to that project, not a concurrent server.')
        finally:
            if managed:
                call(managed + ['kill-server'], env=environment)
            if keeper:
                try:
                    keeper.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    keeper.terminate()
                    keeper.wait(timeout=5)
            call(default + ['kill-server'], env=environment)


if sys.argv[1:2] == ['--probe']:
    probe(*sys.argv[2:])
else:
    exercise()
