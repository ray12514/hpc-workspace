"""Exercise actual Readline completion and fzf history selection in a PTY."""
import errno
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import signal
import struct
import termios
import time

ANSI = re.compile(rb'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))')
captured = Path('/tmp/readline-captured')
marker = Path('/tmp/fzf-must-not-execute')
history = Path(os.environ['XDG_STATE_HOME']) / 'bash-history'
history.write_text('touch /tmp/fzf-must-not-execute\n: fixture-history-tail\n')
child, master = pty.fork()
if child == 0:
    fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 100, 0, 0))
    os.execv('/bin/bash', ['bash', '--noprofile', '--rcfile', '/opt/workspace/config/bashrc', '-i'])

output = bytearray()


def read_until(needle):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if needle in ANSI.sub(b'', bytes(output)).replace(b'\r', b''):
            return
        ready, _, _ = select.select([master], [], [], 0.1)
        if ready:
            try:
                chunk = os.read(master, 65536)
                output.extend(chunk)
                if b'\x1b[6n' in chunk:
                    os.write(master, b'\x1b[1;1R')
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                break
    raise AssertionError('Expected terminal output ' + repr(needle) + ': ' +
                         repr(ANSI.sub(b'', bytes(output))[-1500:]))


def capture(command):
    captured.unlink(missing_ok=True)
    os.write(master, command + b'\x18\x14')
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if captured.exists():
            value = captured.read_text()
            if value:
                return value
        ready, _, _ = select.select([master], [], [], 0.1)
        if ready:
            os.read(master, 65536)
    raise AssertionError('Readline did not capture the selected input')


try:
    read_until(b'$ ')
    output.clear()
    setup = (
        " PS1='READY> '; PROMPT_COMMAND=; "
        "builtin fc -lnr -2147483648 > /tmp/fzf-fixture-history; "
        "_capture() { printf '%s' \"$READLINE_LINE\" > /tmp/readline-captured; READLINE_LINE=''; READLINE_POINT=0; }; "
        "bind -x '\"\\C-x\\C-t\":_capture'\n"
    )
    os.write(master, setup.encode())
    read_until(b'\nREADY> ')
    assert 'touch /tmp/fzf-must-not-execute' in Path('/tmp/fzf-fixture-history').read_text()
    output.clear()
    os.write(master, b'fzf-must-not-execute\x12')
    read_until(b'touch /tmp/fzf-must-not-execute')
    output.clear()
    os.write(master, b'\r')
    read_until(b'READY> ')
    assert capture(b'') == 'touch /tmp/fzf-must-not-execute'
    assert not marker.exists(), 'History selection executed the command'
    assert capture(b'git chec\t').strip() == 'git checkout'
    print('Real PTY: Ctrl-R opens fzf, selection remains editable, and Git Tab completion works.')
finally:
    os.kill(child, signal.SIGKILL)
    os.waitpid(child, 0)
    os.close(master)
