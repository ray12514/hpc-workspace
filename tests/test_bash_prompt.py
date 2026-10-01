"""Workspace prompt still identifies the session when site startup owns its hook."""
import errno
import os
from pathlib import Path
import pty
import re
import select
import signal
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHIPPED_BASHRC = Path('/workspace-tools/config/bashrc')
BASHRC = SHIPPED_BASHRC if SHIPPED_BASHRC.is_file() else ROOT / 'image/config/bashrc'
TOOL_ROOT = Path('/workspace-tools') if BASHRC == SHIPPED_BASHRC else ROOT
ANSI = re.compile(rb'\x1b\[[0-9;]*m')


class PromptStartupTests(unittest.TestCase):
    def test_readonly_site_prompt_command_keeps_workspace_label(self):
        with tempfile.TemporaryDirectory(prefix='ws-prompt-') as temporary:
            root = Path(temporary)
            init = root / 'modules/init'
            init.mkdir(parents=True)
            (init / 'bash').write_text("PROMPT_COMMAND='echo SITE_HOOK'\nreadonly PROMPT_COMMAND\nmodule() { :; }\n")
            (root / 'home').mkdir()
            (root / 'state').mkdir()
            environment = {'PATH': '/usr/bin:/bin', 'HOME': str(root / 'home'),
                           'TERM': 'xterm-256color', 'WS_COLOR': '256', 'WS_GIT_PROMPT': '0',
                           'WS_LAYOUT': 'thin-v1', 'WS_ROOT': str(TOOL_ROOT),
                           'WS_SITE': 'fixture', 'WS_CONTEXT': 'login',
                           'WS_HOSTNAME': 'test-node', 'WS_STATE_HOME': str(root / 'state'),
                           'MODULESHOME': str(root / 'modules'), 'LMOD_CMD': '/nonexistent'}
            child, master = pty.fork()
            if child == 0:
                os.execve('/bin/bash', ['bash', '--noprofile', '--rcfile',
                                         str(BASHRC), '-i'], environment)
            output = bytearray()

            def read_prompt():
                output.clear()
                deadline = time.monotonic() + 10
                while b'$ ' not in output and time.monotonic() < deadline:
                    if select.select([master], [], [], .2)[0]:
                        try:
                            output.extend(os.read(master, 65536))
                        except OSError as exc:
                            if exc.errno != errno.EIO:
                                raise
                            break
                self.assertIn(b'$ ', output, output)
                return bytes(output)

            try:
                initial = read_prompt()
                self.assertNotIn(b'PROMPT_COMMAND: readonly variable', initial)
                self.assertIn(b'SITE_HOOK', initial)
                self.assertIn(b'\x1b[38;5;80m', initial)
                self.assertIn(b'ws:fixture login@test-node', ANSI.sub(b'', initial))
                os.write(master, b'cd /tmp\n')
                moved = read_prompt()
                self.assertIn(b'ws:fixture login@test-node  /tmp', ANSI.sub(b'', moved))
            finally:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
                os.close(master)


if __name__ == '__main__':
    unittest.main()
