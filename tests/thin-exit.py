"""Drive packaged tmux through a real terminal and verify ordinary shell exit."""
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import tempfile
import termios
import time


def check_exit(split, keys):
    name = 'ws-exit-{}-{}'.format(os.getpid(), 'split' if split else 'single')
    base = ['tmux', '-L', name]
    environment = dict(os.environ)
    environment.pop('TMUX', None)
    environment.pop('TMUX_PANE', None)
    with tempfile.TemporaryDirectory(prefix='tmux-exit-') as temporary:
        marker = Path(temporary) / 'ready'
        child, terminal = pty.fork()
        if child == 0:
            os.execvpe(base[0], base + ['new-session', '-s', 'exit-check'], environment)
        status = None
        fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))

        def pump():
            nonlocal status
            if select.select([terminal], [], [], 0.05)[0]:
                try:
                    os.read(terminal, 65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
            if status is None:
                pid, result = os.waitpid(child, os.WNOHANG)
                if pid:
                    status = result

        def wait_for(predicate, message):
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                pump()
                if predicate():
                    return
            panes = subprocess.run(base + ['list-panes', '-a', '-F', '#{pane_id}:dead=#{pane_dead}'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            visible = subprocess.run(base + ['capture-pane', '-p'], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
            raise AssertionError('{}; panes={}; client_alive={}; screen={!r}'.format(
                message, panes.stdout.strip(), status is None, visible.stdout[-1600:]))

        def panes():
            result = subprocess.run(base + ['list-panes', '-a', '-F', '#{pane_dead}'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout.splitlines() if result.returncode == 0 else []

        def ready():
            marker.unlink(missing_ok=True)
            os.write(terminal, ('printf ready > ' + str(marker) + '\n').encode())
            wait_for(marker.exists, 'The shell did not accept keyboard input')
            # A marker can be written before Bash finishes its prompt hooks.
            # Send EOF only at an empty, ready prompt, as a user would.
            def prompt():
                visible = subprocess.run(base + ['capture-pane', '-p'], stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True)
                return visible.stdout.rstrip().endswith('$')
            wait_for(prompt, 'The shell did not return to an empty prompt')

        try:
            wait_for(lambda: panes() == ['0'], 'Tmux did not start a live pane')
            ready()
            # Ctrl-C interrupts; it must leave the shell usable.
            os.write(terminal, b'\x03')
            ready()
            if split:
                subprocess.run(base + ['split-window', '-h', '-t', 'exit-check'], check=True)
                wait_for(lambda: panes() == ['0', '0'], 'The second pane did not start')
                ready()
                os.write(terminal, keys)
                wait_for(lambda: panes() == ['0'], 'Exiting one shell left a dead pane')
                assert status is None, 'Exiting one pane closed the remaining live pane'
                ready()
            os.write(terminal, keys)
            wait_for(lambda: status is not None, 'Exiting the last shell left the terminal attached')
            assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, status
            assert not panes(), 'Tmux retained a dead pane after its last shell exited'
        finally:
            subprocess.run(base + ['kill-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if status is None:
                os.waitpid(child, 0)
            os.close(terminal)


check_exit(False, b'\x04')
check_exit(True, b'exit\n')
print('PASS: Ctrl-C leaves a working shell; Ctrl-D/exit remove closed panes and return the final attached terminal.')
