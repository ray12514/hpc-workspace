"""Real PTY prompts and editor theme checks; names must remain plain data."""
import errno
import os
from pathlib import Path
import pty
import re
import select
import signal
import subprocess
import time

ANSI = re.compile(rb'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))')
project = Path('/project') / 'literal$(touch PWN_PATH)'
project.mkdir(exist_ok=True)
subprocess.run(['git', 'init', '-q', str(project)], check=True)
subprocess.run(['git', '-C', str(project), 'symbolic-ref', 'HEAD',
                'refs/heads/branch$(touch${IFS}PWN_BRANCH)'], check=True)


def prompt(extra):
    child, master = pty.fork()
    if child == 0:
        os.chdir(project)
        environment = dict(os.environ, WS_SITE='jean', WS_CONTEXT='compute',
                           WS_HOSTNAME='fixture-node', SLURM_JOB_ID='12345', WS_GPU_MODE='none')
        environment.pop('NO_COLOR', None)
        environment.pop('COLORTERM', None)
        environment.update(extra)
        os.execve('/bin/bash', ['bash', '--noprofile', '--rcfile', '/opt/workspace/config/bashrc', '-i'], environment)
    output = bytearray()

    def read_until(needle):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if needle in ANSI.sub(b'', bytes(output)):
                return
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
        raise AssertionError('Prompt did not arrive: ' + repr(bytes(output)))

    try:
        read_until(b'$ ')
        initial = bytes(output)
        output.clear()
        os.write(master, b'false\n')
        read_until(b'exit:1 ')
        os.write(master, b'exit\n')
        os.waitpid(child, 0)
        child = None
        return initial, bytes(output)
    finally:
        if child:
            os.kill(child, signal.SIGKILL)
            os.waitpid(child, 0)
        os.close(master)


for extra, expected in (({'WS_COLOR': '256'}, b'\x1b[38;5;80m'),
                         ({'COLORTERM': 'truecolor'}, b'\x1b[38;2;86;182;194m'),
                         ({'NO_COLOR': '1'}, None),
                         ({'WS_COLOR': 'never'}, None),
                         ({'TERM': 'dumb'}, None)):
    initial, failed = prompt(extra)
    plain = ANSI.sub(b'', initial)
    assert b'ws:jean compute@fixture-node job:12345' in plain, plain
    assert b'literal$(touch PWN_PATH)' in plain, plain
    assert b'branch$(touch${IFS}PWN_BRANCH)' in plain, plain
    assert b'exit:1 ' in ANSI.sub(b'', failed)
    if expected:
        assert expected in initial, initial
    else:
        assert not re.search(rb'\x1b\[[0-9;]*m', initial), initial
    assert not (project / 'PWN_PATH').exists(), 'Path executed in prompt'
    assert not (project / 'PWN_BRANCH').exists(), 'Branch executed in prompt'
print('Bash PTY: site/node/job, branch, exit status, color fallbacks, and literal names passed.')

for mode, truecolor, themed in (('256', False, True), ('truecolor', True, True), ('never', False, False)):
    environment = dict(os.environ, WS_COLOR=mode)
    environment.pop('NO_COLOR', None)
    checks = ['assert(vim.o.termguicolors == ' + str(truecolor).lower() + ')',
              'assert((vim.g.colors_name == "workspace") == ' + str(themed).lower() + ')']
    if themed:
        checks.append('assert(vim.api.nvim_get_hl(0, {name="Function", link=false}).ctermfg == 75)')
    result = subprocess.run(['nvim', '--headless', '+lua ' + '; '.join(checks), '+qa'],
                            env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and 'Error' not in result.stderr, result.stderr
print('Neovim: 256-color, true-color, and theme opt-out passed.')
