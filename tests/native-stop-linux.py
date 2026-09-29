"""Test host-only UID cleanup inside an isolated disposable Linux container.

Run as container root, with a read-only /src mount and no host PID namespace.
The cleaner itself runs as UID 1000 under a real interactive Bash/PTTY. The
fixture's root supervisor and UID 1001 workload must remain alive.
"""
import importlib.machinery
import contextlib
import io
import os
import pty
import select
import signal
import subprocess
import sys
import time
from unittest.mock import patch

HELPER = '/src/scripts/stop-own-node-processes'


def account(uid):
    def change():
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)
    return change


def user_test():
    assert os.getuid() == 1000
    workloads = []
    shell = master = None
    captured = bytearray()

    def expect(marker):
        wanted = marker.encode()
        deadline = time.monotonic() + 15
        while wanted not in captured and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], .1)
            if ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                captured.extend(data)
        assert wanted in captured, captured.decode(errors='replace')[-3000:]
        del captured[:captured.index(wanted) + len(wanted)]

    def send(line):
        os.write(master, (line + '\n').encode())

    try:
        normal = subprocess.Popen(['/bin/sleep', '60'])
        workloads.append(normal)
        stubborn = subprocess.Popen([sys.executable, '-u', '-c',
            'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(60)'],
            stdout=subprocess.PIPE)
        workloads.append(stubborn)
        assert stubborn.stdout.readline() == b'ready\n'
        nondumpable = subprocess.Popen([sys.executable, '-u', '-c',
            'import ctypes,time; assert ctypes.CDLL(None).prctl(4,0,0,0,0)==0; '
            'print("ready",flush=True); time.sleep(60)'], stdout=subprocess.PIPE)
        workloads.append(nondumpable)
        assert nondumpable.stdout.readline() == b'ready\n'
        old_shell = subprocess.Popen(['/bin/bash', '--noprofile', '--norc', '-c', 'sleep 60 & wait'])
        workloads.append(old_shell)
        refused = subprocess.run([sys.executable, HELPER, '--stop'],
                                 env=dict(os.environ, TMUX='/tmp/synthetic-session'),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        assert refused.returncode == 2
        assert all(job.poll() is None for job in workloads)
        shell, master = pty.fork()
        if shell == 0:
            os.environ['PS1'] = 'NATIVE_READY> '
            os.execv('/bin/bash', ['/bin/bash', '--noprofile', '--norc', '-i'])
        expect('NATIVE_READY> ')
        send('stty -echo')
        expect('NATIVE_READY> ')
        send('python3 ' + HELPER + '; printf "PREVIEW_RC=%s\\n" "$?"')
        expect('Preview only.')
        expect('PREVIEW_RC=0\r\n')
        assert all(job.poll() is None for job in workloads)
        send('python3 ' + HELPER + ' --stop --grace-seconds 1; printf "STOP_RC=%s\\n" "$?"')
        expect('CLEANUP_OK:')
        expect('STOP_RC=0\r\n')
        assert normal.wait(timeout=3) == -signal.SIGTERM
        assert stubborn.wait(timeout=3) == -signal.SIGKILL
        assert nondumpable.wait(timeout=3) == -signal.SIGTERM
        old_shell.wait(timeout=3)
        send('printf "PRESERVED_NATIVE_SHELL_OK\\n"')
        expect('PRESERVED_NATIVE_SHELL_OK\r\n')
        send('exit 0')
        _, status = os.waitpid(shell, 0)
        shell = None
        assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
        print('PASS: preview preserves workloads; TERM/KILL stop old tasks including a nondumpable task; current Bash and caller survive.')
    finally:
        if master is not None:
            os.close(master)
        if shell is not None and shell > 0:
            os.kill(shell, signal.SIGKILL)
            os.waitpid(shell, 0)
        for job in workloads:
            if job.poll() is None:
                job.kill()
            job.wait()


def supervisor():
    assert os.getuid() == 0, 'Use only the disposable container fixture'
    # These narrow checks exercise signal-target races without sending signals.
    module = importlib.machinery.SourceFileLoader('native_cleanup', HELPER).load_module()
    original = dict(pid=123, uid=1000, start='1', state='S')
    for changed in (dict(original, start='2'), dict(original, uid=1001), dict(original, state='Z')):
        with patch.object(module, 'process', return_value=changed), patch.object(module.os, 'kill') as kill:
            assert module.deliver([original], signal.SIGKILL, 1000, {}) == []
            kill.assert_not_called()
    with patch.object(module.os, 'kill') as kill:
        module.deliver([original], signal.SIGKILL, 1000, {123: original})
        kill.assert_not_called()
    # Simulate an unexited kernel waiter: signal delivery is not exit proof.
    blocked = dict(original, ppid=1, name='blocked-fixture', state='D')
    with patch.dict(os.environ, {}, clear=True), \
            patch.object(sys, 'argv', [HELPER, '--stop']), \
            patch.object(module.os, 'getuid', return_value=1000), \
            patch.object(module.os, 'geteuid', return_value=1000), \
            patch.object(module, 'ancestors', return_value={}), \
            patch.object(module, 'targets', return_value=([blocked], [])), \
            patch.object(module, 'wait_remaining', return_value=([blocked], [])), \
            patch.object(module, 'deliver', return_value=[]) as deliver, \
            contextlib.redirect_stdout(io.StringIO()) as output:
        assert module.main() == 3
        assert 'CLEANUP INCOMPLETE' in output.getvalue()
        assert 'CLEANUP_OK' not in output.getvalue()
        assert [call.args[1] for call in deliver.call_args_list] == [signal.SIGTERM, signal.SIGKILL]
    with patch.dict(os.environ, {}, clear=True), \
            patch.object(sys, 'argv', [HELPER, '--stop']), \
            patch.object(module.os, 'getuid', return_value=1000), \
            patch.object(module.os, 'geteuid', return_value=1000), \
            patch.object(module, 'ancestors', return_value={}), \
            patch.object(module, 'targets', return_value=([], ['unreadable fixture'])), \
            patch.object(module, 'deliver') as deliver, \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert module.main() == 2
        deliver.assert_not_called()
    refused = subprocess.run([sys.executable, HELPER, '--stop'], capture_output=True, timeout=5)
    assert refused.returncode == 2, refused.stderr
    other_user = subprocess.Popen(['/bin/sleep', '60'], preexec_fn=account(1001))
    try:
        result = subprocess.run([sys.executable, __file__, '--user-test'],
                                preexec_fn=account(1000), timeout=30)
        assert result.returncode == 0, result.returncode
        assert other_user.poll() is None, 'Another account was affected'
        print('PASS: root refused; another UID survives; stale PID identity, changed owner, zombies and ancestors are not signalled.')
        print('PASS: simulated persistent D wait reports incomplete; inspection failure prevents stop signals.')
    finally:
        other_user.terminate()
        other_user.wait(timeout=5)


if __name__ == '__main__':
    if sys.argv[1:] == ['--user-test']:
        user_test()
    else:
        supervisor()
