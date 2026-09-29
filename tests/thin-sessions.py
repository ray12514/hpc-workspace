"""Offline Linux/Apptainer regression: two workspaces, live tasks, reconnect, stop.

Run only in the disposable native test fixture, with source at /src and a SIF
argument. Uses isolated home/state/projects and never contacts an agent service.
"""
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

root = Path(tempfile.mkdtemp(prefix='ws-session-test-'))
home = Path(tempfile.mkdtemp(prefix='ws-session-home-', dir=str(Path.home())))
state, native = [root / item for item in ('state', 'bin')]
projects = [root / 'project A', root / 'project B']
for path in [state, native] + projects:
    path.mkdir()
runtime = shutil.which('apptainer')
# Nested SIF mounts are unavailable in this Docker fixture. Extract once, then
# use that same immutable toolkit for each real Apptainer invocation. Repeated
# --unsquash clients otherwise exhaust the fixture's disk during concurrent use.
sandbox = root / 'image'
print('Preparing one extracted SIF for the disposable multi-session fixture.', flush=True)
extract = subprocess.run([runtime, 'build', '--sandbox', str(sandbox), sys.argv[1]],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
assert extract.returncode == 0, extract.stderr.decode(errors='replace')[-3000:]
wrapper = native / 'apptainer'
wrapper.write_text('#!' + sys.executable + '\nimport os,sys\n'
                   'args = [' + repr(str(sandbox)) + ' if arg == ' + repr(sys.argv[1]) +
                   ' else arg for arg in sys.argv[1:]]\n'
                   'os.execv(' + repr(runtime) + ', [' + repr(runtime) + '] + args)\n')
wrapper.chmod(0o700)
environment = dict(os.environ, HOME=str(home), WS_CONFIG_DIR=str(home / '.config/hpc-workspace'),
                   PATH=str(native) + ':' + os.environ['PATH'], TERM='xterm-256color',
                   LANG='C.UTF-8', PYTHONDONTWRITEBYTECODE='1')
entry = [sys.executable, '/src/bin/ws']
clients, records = [], []


def run(arguments, timeout=90, expect=0):
    result = subprocess.run(entry + arguments, cwd=root, env=environment,
                            universal_newlines=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    assert result.returncode == expect, (arguments[:4], result.returncode,
                                         result.stdout[-2000:], result.stderr[-2000:])
    return result.stdout


def common(project):
    return ['--project', str(project), '--image', sys.argv[1], '--state-dir', str(state)]


def tmux(record, *arguments):
    return run(['enter'] + common(Path(record['project'])) +
               ['--', 'tmux', '-N', '-L', record['session']] + list(arguments))


def attachment(arguments, marker, label):
    started = time.monotonic()
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(root)
        os.execve(entry[0], entry + arguments, environment)
    client = (pid, master)
    clients.append(client)
    captured = bytearray()
    while time.monotonic() - started < 75:
        ready, _, _ = select.select([master], [], [], .1)
        if ready:
            try:
                part = os.read(master, 65536)
            except OSError:
                break
            if not part:
                break
            captured.extend(part)
            if marker.encode() in captured:
                print(json.dumps({'case': label, 'seconds': round(time.monotonic() - started, 2)}), flush=True)
                return client
    raise AssertionError((label, captured.decode(errors='replace')[-4000:]))


def attach(record, label, detach_others=False):
    args = ['attach', '--session', record['session'], '--state-dir', str(state)]
    if detach_others:
        args.append('--detach-others')
    return attachment(args, 'RUNNING_' + Path(record['project']).name, label)


def close_client(client, detach=False, already_detached=False):
    pid, master = client
    if detach:
        os.write(master, b'\x02d')
    elif not already_detached:
        os.close(master)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if os.waitpid(pid, os.WNOHANG)[0]:
            break
        time.sleep(.1)
    else:
        os.kill(pid, signal.SIGTERM)
        os.waitpid(pid, 0)
        if detach or already_detached:
            raise AssertionError('Client failed to detach')
    if detach or already_detached:
        os.close(master)
    clients.remove(client)


def identity(pid):
    try:
        fields = Path('/proc/{}/stat'.format(pid)).read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except OSError:
        return None


def check_task(project, expected_pid):
    assert (project / 'task-pid').read_text() == expected_pid
    before = (project / 'heartbeat').read_text()
    time.sleep(.4)
    assert (project / 'heartbeat').read_text() != before


try:
    for project in projects:
        print('Starting ' + project.name, flush=True)
        run(['session'] + common(project) + ['--detach'])
        record = next(json.loads(path.read_text()) for path in (state / 'session-hosts').glob('*/*.json')
                      if json.loads(path.read_text())['project'] == str(project))
        records.append(record)
        task = project / 'task.py'
        task.write_text('import os,time\nfrom pathlib import Path\n'
                        'Path("task-pid").write_text(str(os.getpid()))\n'
                        'while True:\n'
                        '    Path("heartbeat").write_text(str(time.monotonic()))\n'
                        '    print(' + repr('RUNNING_' + project.name) + ', flush=True)\n'
                        '    time.sleep(.2)\n')
        tmux(record, 'send-keys', '-t', record['session'] + ':workspace',
             'python3 -u ' + shlex.quote(str(task)), 'Enter')
        client = attach(record, 'attach ' + project.name)
        close_client(client, detach=True)

    pids = [(project / 'task-pid').read_text() for project in projects]
    assert len(list((state / 'session-hosts').glob('*/*.json'))) == 2
    run(['attach', '--state-dir', str(state)], expect=2)  # Never guess between two workspaces.
    run(['attach', '--session', records[0]['session'], '--state-dir', str(state), '--check'])
    first = attach(records[0], 'return to A while B runs')
    close_client(first)  # Terminal loss, not a normal detach.
    recovered = attach(records[0], 'recover A after terminal loss')
    replacement = attach(records[0], 'replace stale A client', detach_others=True)
    close_client(recovered, already_detached=True)  # -d must have detached this client itself.
    close_client(replacement, detach=True)
    for project, pid in zip(projects, pids):
        check_task(project, pid)
    for record in records:
        assert identity(record['pid']) == record['identity']

    print('Testing a separate foreground container while both managed workspaces run.', flush=True)
    run(['enter'] + common(projects[0]) + ['--', '/bin/sh', '-c', 'printf FOREGROUND_EXIT_OK'])
    for project, pid in zip(projects, pids):
        check_task(project, pid)

    print('Probing Codex sandbox inside managed tmux; no API call or credentials.', flush=True)
    sandbox_script = projects[1] / 'sandbox.sh'
    sandbox_script.write_text('#!/bin/sh\ncd ' + shlex.quote(str(projects[1])) + '\n'
                              'prefix=${1:-tmux}\n'
                              'codex --version > "$prefix-version.txt" 2>&1\n'
                              'codex sandbox --config sandbox_mode="\\\"workspace-write\\\"" '
                              '-- /bin/sh -c "printf SANDBOX_OK; touch sandbox-write-ok" '
                              '> "$prefix-result.txt" 2>&1\n'
                              'printf "%s" "$?" > "$prefix-status"\n')
    # A separate window leaves the live task in the workspace pane untouched.
    tmux(records[1], 'new-window', '-d', '-t', records[1]['session'], '-n', 'sandbox-probe',
         '/bin/sh ' + shlex.quote(str(sandbox_script)))
    deadline = time.monotonic() + 25
    while not (projects[1] / 'tmux-status').exists() and time.monotonic() < deadline:
        time.sleep(.1)
    assert (projects[1] / 'tmux-status').exists(), 'Sandbox probe did not finish'
    run(['enter'] + common(projects[1]) + ['--', '/bin/sh', str(sandbox_script), 'foreground'])
    for prefix in ('tmux', 'foreground'):
        print(json.dumps({'sandbox_context': prefix,
                          'codex': (projects[1] / (prefix + '-version.txt')).read_text().strip(),
                          'sandbox_status': (projects[1] / (prefix + '-status')).read_text(),
                          'sandbox_output': (projects[1] / (prefix + '-result.txt')).read_text()[-2500:]}), flush=True)

    print('Stopping only A.', flush=True)
    run(['stop', '--session', records[0]['session'], '--state-dir', str(state)])
    assert identity(records[0]['pid']) != records[0]['identity']
    assert identity(int(pids[0])) is None, 'A task still runs after stopping A'
    run(['attach', '--session', records[0]['session'], '--state-dir', str(state)], expect=2)
    check_task(projects[1], pids[1])
    final = attach(records[1], 'B remains attachable after stopping A')
    close_client(final, detach=True)
    run(['stop', '--project', str(projects[1]), '--state-dir', str(state)])
    assert identity(records[1]['pid']) != records[1]['identity']
    assert identity(int(pids[1])) is None
    print('PASS: switching, normal detach, terminal loss, separate entry, and targeted stop preserve the other workspace.', flush=True)
finally:
    for client in clients[:]:
        close_client(client)
    for record in records:
        if identity(record['pid']) == record['identity']:
            try:
                tmux(record, 'kill-server')
            except Exception:
                pass
