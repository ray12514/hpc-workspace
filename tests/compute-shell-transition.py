"""Offline thin-image PTY smoke test; scheduler placement is simulated.

Run in the disposable toolkit fixture with this checkout mounted at /src.
No scheduler, CSE build, credentials, or API calls are used.
"""
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import time


if sys.argv[1:] == ['--simulated-step']:
    assert 'WS_CONTAINER' not in os.environ
    assert 'TMUX' not in os.environ and 'TMUX_PANE' not in os.environ
    assert not any(p.startswith('/workspace-tools') for p in os.environ['PATH'].split(':'))
    assert os.environ['COMPUTE_PROBE_SENTINEL'] == 'synthetic-module-setting'
    assert os.environ['COMPUTE_PROBE_TOKEN'] == 'synthetic-not-a-real-key'
    os.environ.update(SLURM_JOB_ID='fixture-only', SLURM_CPUS_PER_TASK='2', PS1='STEP_READY> ')
    os.execve('/bin/bash', ['/bin/bash', '--noprofile', '--norc', '-i'], os.environ)

if sys.argv[1:] == ['--compute-workspace']:
    assert os.environ['WS_CONTAINER'] == '1'
    assert os.environ['WS_CONTEXT'] == 'compute'
    assert os.environ['SLURM_JOB_ID'] == 'fixture-only'
    result = subprocess.run(['ws', 'agent', 'codex', '--native', '--', '--version'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert b'codex' in result.stdout.lower(), result.stdout
    print('COMPUTE_ENTRY_AND_CODEX_VERSION_OK', flush=True)
    sys.exit(0)

assert os.environ.get('WS_CONTAINER') == '1', 'Run inside the thin toolkit fixture'
environment = dict(os.environ, COMPUTE_PROBE_SENTINEL='synthetic-module-setting',
                   COMPUTE_PROBE_TOKEN='synthetic-not-a-real-key',
                   TMUX='/tmp/synthetic-login-socket,1,0', TMUX_PANE='%0')
script = str(Path(__file__).resolve())
child = None
master = None
captured = bytearray()


def expect(marker, timeout=30):
    deadline = time.monotonic() + timeout
    wanted = marker.encode()
    while wanted not in captured and time.monotonic() < deadline:
        readable, _, _ = select.select([master], [], [], .1)
        if readable:
            try:
                part = os.read(master, 65536)
            except OSError:
                break
            if not part:
                break
            captured.extend(part)
    assert wanted in captured, (marker, captured.decode(errors='replace')[-1500:])
    del captured[:captured.index(wanted) + len(wanted)]


def send(command):
    os.write(master, (command + '\n').encode())


try:
    with tempfile.TemporaryDirectory(prefix='compute-shell-probe-') as folder:
        child, master = pty.fork()
        if child == 0:
            os.execve('/workspace-tools/bin/ws', ['ws', 'job-env', '--', sys.executable,
                                                 '-I', script, '--simulated-step'], environment)
        expect('STEP_READY> ')
        send('stty -echo')
        expect('STEP_READY> ')
        send('cd ' + shlex.quote(folder) + '; probe_shell_pid=$$; probe_value=retained; '
             "printf 'FIRST_COMMAND_OK\\n'")
        expect('FIRST_COMMAND_OK\r\n')
        send('sleep 0.2; test "$probe_shell_pid" = "$$" && test "$probe_value" = retained && '
             'test "$PWD" = ' + shlex.quote(folder) + ' && '
             "printf 'SECOND_COMMAND_SAME_SHELL_OK\\n'")
        expect('SECOND_COMMAND_SAME_SHELL_OK\r\n')
        send('/workspace-tools/thin-entry /workspace-tools/libexec/python3 -I ' +
             shlex.quote(script) + ' --compute-workspace')
        expect('COMPUTE_ENTRY_AND_CODEX_VERSION_OK\r\n')
        send('exit 7')
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            pid, status = os.waitpid(child, os.WNOHANG)
            if pid:
                child = None
                assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 7, status
                break
            time.sleep(.1)
        assert child is None, 'Launcher did not propagate the compute shell exit'
        print('PASS: real PTY persists across commands; job environment is restored; '
              'synthetic compute context and packaged Codex --version work; exit status propagates.')
        print('NOT TESTED: real Slurm, separate compute host, CSE group/mounts, gateway API, build speed.')
finally:
    if master is not None:
        os.close(master)
    if child is not None and child > 0:
        os.kill(child, signal.SIGKILL)
        os.waitpid(child, 0)
