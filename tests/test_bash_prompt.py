"""Workspace prompt still identifies the session when site startup owns its hook."""
import errno
import os
from pathlib import Path
import pty
import re
import select
import shutil
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
    def read_prompt(self, master, markers=(b'$ ',)):
        output = bytearray()
        deadline = time.monotonic() + 10
        while not any(marker in output for marker in markers) and time.monotonic() < deadline:
            if select.select([master], [], [], .2)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
        self.assertTrue(any(marker in output for marker in markers), output)
        return bytes(output)

    def read_completed_command(self, master, marker):
        output = bytearray()
        deadline = time.monotonic() + 10
        line = re.compile(rb'(?m)(?:^|\r)' + re.escape(marker) + rb'\r?\n')
        while time.monotonic() < deadline:
            if select.select([master], [], [], .2)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
                if line.search(bytes(output)):
                    return bytes(output)
        self.fail('Prompt command did not finish: ' + repr(bytes(output[-500:])))

    def test_readonly_site_prompt_command_keeps_workspace_label(self):
        with tempfile.TemporaryDirectory(prefix='ws-prompt-') as temporary:
            root = Path(temporary)
            init = root / 'modules/init'
            init.mkdir(parents=True)
            (init / 'bash').write_text("PROMPT_COMMAND='echo SITE_HOOK'\nreadonly PROMPT_COMMAND\nmodule() { :; }\n")
            (root / 'home').mkdir()
            (root / 'state').mkdir()
            zoxide = shutil.which('zoxide')
            path = '/usr/bin:/bin'
            if zoxide:
                path = str(Path(zoxide).parent) + ':' + path
            environment = {'PATH': path, 'HOME': str(root / 'home'),
                           'TERM': 'xterm-256color', 'WS_COLOR': '256', 'WS_GIT_PROMPT': '0',
                           'WS_LAYOUT': 'thin-v1', 'WS_ROOT': str(TOOL_ROOT),
                           'WS_SITE': 'fixture', 'WS_CONTEXT': 'login',
                           'WS_HOSTNAME': 'test-node', 'WS_STATE_HOME': str(root / 'state'),
                           'MODULESHOME': str(root / 'modules'), 'LMOD_CMD': '/nonexistent'}
            child, master = pty.fork()
            if child == 0:
                os.execve('/bin/bash', ['bash', '--noprofile', '--rcfile',
                                         str(BASHRC), '-i'], environment)
            try:
                initial = self.read_prompt(master)
                self.assertNotIn(b'PROMPT_COMMAND: readonly variable', initial)
                self.assertIn(b'SITE_HOOK', initial)
                self.assertIn(b'\x1b[38;5;80m', initial)
                self.assertIn(b'ws:fixture login@test-node', ANSI.sub(b'', initial))
                if zoxide:
                    os.write(master, b'type -t z\n')
                    self.assertIn(b'function', self.read_prompt(master))
                os.write(master, b'cd /tmp\n')
                moved = self.read_prompt(master)
                self.assertIn(b'ws:fixture login@test-node  /tmp', ANSI.sub(b'', moved))
            finally:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
                os.close(master)

    def test_late_readonly_compound_hook_keeps_workspace_label(self):
        with tempfile.TemporaryDirectory(prefix='ws-compound-prompt-') as temporary:
            root = Path(temporary)
            home = root / 'home'
            personal = home / '.config/hpc-workspace'
            personal.mkdir(parents=True)
            (personal / 'bashrc').write_text(
                "PROMPT_COMMAND='PS1=\"SITE> \"; printf \"SITE_HOOK\\n\"'\n"
                "readonly PROMPT_COMMAND\n")
            (root / 'state').mkdir()
            environment = {'PATH': '/usr/bin:/bin', 'HOME': str(home),
                           'TERM': 'xterm-256color', 'WS_COLOR': '256',
                           'WS_GIT_PROMPT': '0', 'WS_LAYOUT': 'thin-v1',
                           'WS_ROOT': str(TOOL_ROOT), 'WS_SITE': 'fixture',
                           'WS_CONTEXT': 'login', 'WS_HOSTNAME': 'test-node',
                           'WS_STATE_HOME': str(root / 'state')}
            child, master = pty.fork()
            if child == 0:
                os.execve('/bin/bash', ['bash', '--noprofile', '--rcfile',
                                         str(BASHRC), '-i'], environment)
            try:
                initial = self.read_prompt(master, (b'$ ', b'SITE> '))
                self.assertNotIn(b'PROMPT_COMMAND: readonly variable', initial)
                self.assertIn(b'SITE_HOOK', initial)
                self.assertIn(b'ws:fixture login@test-node', ANSI.sub(b'', initial))
                os.write(master, b'cd /tmp\n')
                moved = self.read_prompt(master, (b'$ ', b'SITE> '))
                self.assertIn(b'SITE_HOOK', moved)
                self.assertIn(b'ws:fixture login@test-node  /tmp', ANSI.sub(b'', moved))
                os.write(master, b'type -t readonly; readonly -p | grep -q PROMPT_COMMAND && echo PROMPT_READONLY; printf "__WS_STATE_DONE__\\n"\n')
                state = self.read_completed_command(master, b'__WS_STATE_DONE__')
                self.assertIn(b'builtin', state)
                self.assertIn(b'PROMPT_READONLY', state)
            finally:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
                os.close(master)

    @unittest.skipUnless(Path('/workspace-tools/thin-shell').is_file(), 'thin image only')
    def test_site_prompt_and_module_survive_workspace_shell_startup(self):
        with tempfile.TemporaryDirectory(prefix='ws-site-prompt-') as temporary:
            root = Path(temporary)
            init = root / 'modules/init'
            init.mkdir(parents=True)
            (init / 'bash').write_text(
                "_site_prompt() { PS1='SITE> '; printf 'SITE_HOOK\\n'; }\n"
                "PROMPT_COMMAND=_site_prompt\nreadonly PROMPT_COMMAND\n"
                "_site_module_helper() { printf 'MODULE_OK\\n'; }\n"
                "module() { _site_module_helper; }\n")
            (root / 'home').mkdir()
            (root / 'state').mkdir()
            environment = {'PATH': '/workspace-tools/bin:/usr/bin:/bin',
                           'HOME': str(root / 'home'), 'TERM': 'xterm-256color',
                           'WS_COLOR': '256', 'WS_GIT_PROMPT': '0',
                           'WS_LAYOUT': 'thin-v1', 'WS_ROOT': '/workspace-tools',
                           'WS_SITE': 'fixture', 'WS_CONTEXT': 'login',
                           'WS_HOSTNAME': 'test-node', 'WS_STATE_HOME': str(root / 'state'),
                           'MODULESHOME': str(root / 'modules'), 'LMOD_CMD': '/nonexistent'}
            child, master = pty.fork()
            if child == 0:
                os.execve('/workspace-tools/thin-shell', ['thin-shell'], environment)
            try:
                initial = self.read_prompt(master)
                self.assertNotIn(b'PROMPT_COMMAND: readonly variable', initial)
                self.assertIn(b'SITE_HOOK', initial)
                self.assertIn(b'ws:fixture login@test-node', ANSI.sub(b'', initial))
                os.write(master, b'module; type -t z; cd /tmp\n')
                moved = self.read_prompt(master)
                self.assertIn(b'MODULE_OK', moved)
                self.assertIn(b'function', moved)
                self.assertIn(b'ws:fixture login@test-node  /tmp', ANSI.sub(b'', moved))
            finally:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
                os.close(master)

    @unittest.skipUnless(Path('/workspace-tools/thin-shell').is_file(), 'thin image only')
    def test_late_readonly_hook_still_shows_workspace_identity(self):
        with tempfile.TemporaryDirectory(prefix='ws-late-prompt-') as temporary:
            root = Path(temporary)
            init = root / 'modules/init'
            init.mkdir(parents=True)
            (init / 'bash').write_text(
                "_site_prompt() { PS1='SITE> '; }\n"
                "PROMPT_COMMAND=_site_prompt\nreadonly PROMPT_COMMAND\n"
                "module() { :; }\n")
            home = root / 'home'
            personal = home / '.config/hpc-workspace'
            personal.mkdir(parents=True)
            (personal / 'bashrc').write_text(
                "PROMPT_COMMAND=(_site_prompt)\nreadonly PROMPT_COMMAND\nPS1='SITE> '\n")
            (root / 'state').mkdir()
            environment = {'PATH': '/workspace-tools/bin:/usr/bin:/bin',
                           'HOME': str(home), 'TERM': 'xterm-256color',
                           'WS_COLOR': '256', 'WS_GIT_PROMPT': '0',
                           'WS_LAYOUT': 'thin-v1', 'WS_ROOT': '/workspace-tools',
                           'WS_SITE': 'fixture', 'WS_CONTEXT': 'login',
                           'WS_HOSTNAME': 'test-node', 'WS_STATE_HOME': str(root / 'state'),
                           'MODULESHOME': str(root / 'modules'), 'LMOD_CMD': '/nonexistent'}
            child, master = pty.fork()
            if child == 0:
                os.execve('/workspace-tools/thin-shell', ['thin-shell'], environment)
            try:
                initial = self.read_prompt(master, (b'$ ', b'SITE> '))
                self.assertNotIn(b'PROMPT_COMMAND: readonly variable', initial)
                self.assertIn(b'ws:fixture login@test-node', ANSI.sub(b'', initial))
                os.write(master, b'cd /tmp\n')
                moved = self.read_prompt(master, (b'$ ', b'SITE> '))
                self.assertIn(b'ws:fixture login@test-node  /tmp', ANSI.sub(b'', moved))
            finally:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
                os.close(master)

    @unittest.skipUnless(Path('/workspace-tools/thin-shell').is_file(), 'thin image only')
    def test_command_shell_execs_a_fresh_workspace_prompt(self):
        with tempfile.TemporaryDirectory(prefix='ws-shell-reentry-') as temporary:
            root = Path(temporary)
            init = root / 'modules/init'
            init.mkdir(parents=True)
            (init / 'bash').write_text(
                "PROMPT_COMMAND='printf \"SITE_HOOK\\n\"'\n"
                "readonly PROMPT_COMMAND\nmodule() { :; }\n")
            (root / 'home').mkdir()
            (root / 'state').mkdir()
            environment = {'PATH': '/workspace-tools/bin:/usr/bin:/bin',
                           'HOME': str(root / 'home'), 'TERM': 'xterm-256color',
                           'WS_COLOR': 'never', 'WS_GIT_PROMPT': '0',
                           'WS_LAYOUT': 'thin-v1', 'WS_ROOT': '/workspace-tools',
                           'WS_SITE': 'fixture', 'WS_CONTEXT': 'login',
                           'WS_HOSTNAME': 'test-node', 'WS_STATE_HOME': str(root / 'state'),
                           'MODULESHOME': str(root / 'modules'), 'LMOD_CMD': '/nonexistent'}
            child, master = pty.fork()
            if child == 0:
                os.execve('/workspace-tools/thin-shell',
                          ['thin-shell', '-c', 'exec /workspace-tools/thin-shell'], environment)
            try:
                initial = self.read_prompt(master)
                self.assertIn(b'ws:fixture login@test-node', ANSI.sub(b'', initial))
                self.assertIn(b'SITE_HOOK', initial)
                os.write(master, b'printf "REENTRY_OK\\n"\n')
                output = self.read_completed_command(master, b'REENTRY_OK')
                self.assertNotIn(b'PROMPT_COMMAND: readonly variable', output)
            finally:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
                os.close(master)


if __name__ == '__main__':
    unittest.main()
