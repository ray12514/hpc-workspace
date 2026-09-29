#!/usr/bin/env python3
"""Live Linux probe check: a vfork wait in D, sleeping server, and CPU quota.

Run in a disposable offline fixture with --cpus 1 and a writable /tmp.
The intentional vfork wait validates D-state reporting, not Blueback's cause.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
children = []
secret = 'diagnostic-secret-must-not-be-collected'
environment = dict(os.environ, DIAGNOSTIC_TEST_SECRET=secret)
environment.pop('WS_CONTAINER', None)
environment.pop('WS_LAYOUT', None)


def start(name, code, *arguments):
    script = 'import ctypes,os,time; ctypes.CDLL(None).prctl(15, {!r}, 0, 0, 0); '.format(name.encode()) + code
    child = subprocess.Popen([sys.executable, '-c', script] + list(arguments), env=environment)
    children.append(child)
    return child


with tempfile.TemporaryDirectory(prefix='workspace-diagnostic-test-') as directory:
    fifo = os.path.join(directory, 'spawn-wait')
    os.mkfifo(fifo)
    report_path = Path(directory) / 'report.json'
    try:
        server = start('tmux: server', 'time.sleep(60)', secret)
        client = start('tmux: client',
            'child = os.posix_spawn("/bin/true", ["/bin/true"], os.environ, '
            'file_actions=[(os.POSIX_SPAWN_OPEN, 3, {!r}, os.O_RDONLY, 0o600)]); '
            'os.waitpid(child, 0)'.format(fifo))
        for _ in range(2):
            start('craycc', 'until=time.monotonic()+60\nwhile time.monotonic()<until: pass', secret)
        deadline = time.monotonic() + 5
        while Path('/proc/{}/stat'.format(client.pid)).read_text().rsplit(')', 1)[1].split()[0] != 'D':
            if time.monotonic() >= deadline:
                raise AssertionError('fixture did not create the intended vfork wait')
            time.sleep(0.05)
        result = subprocess.run([sys.executable, str(root / 'scripts/diagnose-session'),
                                 '--output', str(report_path)], env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=40)
        assert result.returncode == 0, result.stdout + result.stderr
        text = report_path.read_text()
        assert secret not in text + result.stdout + result.stderr
        report = json.loads(text)
        assert len(report['samples']) == 3
        assert report_path.stat().st_mode & 0o777 == 0o600
        for sample in report['samples']:
            observed = next(row for row in sample['processes'] if row['pid'] == client.pid)
            assert observed['state'] == 'D', observed
            assert observed['details']['blocked_threads'], observed
            assert any(row['pid'] == server.pid and row['state'] == 'S' for row in sample['processes'])
        def throttled(sample):
            return sum(int(line.split()[1]) for entry in sample['cpu'].values()
                       for line in entry.get('cpu.stat', '').splitlines() if line.startswith('nr_throttled '))
        assert throttled(report['samples'][-1]) > throttled(report['samples'][0]), result.stdout
        assert all(child.poll() is None for child in children), 'diagnostic changed an existing test process'
        print(result.stdout)
        print('PASS: live D-state client, sleeping server, CPU throttling, private report, unchanged workload.')
    finally:
        try:
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)
