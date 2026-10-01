"""The managed editor window returns to a shell after Neovim exits."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('tmux') and shutil.which('nvim'), 'tmux and nvim required')
class EditorWindowTests(unittest.TestCase):
    def test_quitting_editor_keeps_window_as_shell(self):
        short_tmp = '/private/tmp' if Path('/private/tmp').is_dir() else '/tmp'
        with tempfile.TemporaryDirectory(prefix='we-', dir=short_tmp) as temporary:
            root = Path(temporary)
            tools = root / 'tools'
            for part in ('bin', 'config/tmux'):
                (tools / part).mkdir(parents=True, exist_ok=True)
            (tools / 'bin/tmux').symlink_to(shutil.which('tmux'))
            (tools / 'bin/bash').symlink_to('/bin/bash')
            (tools / 'lib').mkdir()
            (tools / 'lib/integration.py').write_text('''
import hashlib
import os

def session_name(site, project, release):
    key = hashlib.sha256((site + "\\0" + str(project)).encode()).hexdigest()[:12]
    return 'ws-' + key + '-' + hashlib.sha256(release.encode()).hexdigest()[:8]

def process_identity(pid):
    try:
        os.kill(pid, 0)
        return str(pid)
    except ProcessLookupError:
        return None
''')
            (tools / 'config/tmux/tmux.conf').write_text('set -g remain-on-exit off\n')
            shell = tools / 'thin-shell'
            shell.write_text('#!/bin/bash\nexec /bin/bash --noprofile --norc -i "$@"\n')
            shell.chmod(0o700)
            project = root / 'project'
            project.mkdir()
            (project / 'sample.txt').write_text('sample\n')
            script = root / 'thin-session'
            script.write_text((ROOT / 'scripts/thin-session').read_text().replace('/workspace-tools', str(tools)))
            state = root / 'state'
            environment = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / 'config'),
                               XDG_DATA_HOME=str(root / 'data'), XDG_STATE_HOME=str(root / 'xdg-state'),
                               WS_STATE_HOME=str(state), WS_RELEASE='editor-test', WS_SITE='local',
                               TERM='xterm-256color', TMUX_TMPDIR=str(root))
            environment.pop('TMUX', None)
            environment.pop('TMUX_PANE', None)
            ready = root / 'ready.json'
            keeper = subprocess.Popen([shutil.which('python3'), str(script), '--serve', str(ready)],
                                      cwd=project, env=environment, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
            base = None
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and time.monotonic() < deadline:
                    if keeper.poll() is not None:
                        self.fail('Managed launch exited: ' + keeper.communicate()[1])
                    time.sleep(.05)
                self.assertTrue(ready.exists(), 'Managed launch never became ready')
                name = json.loads(ready.read_text())['session']
                base = [shutil.which('tmux'), '-L', name]
                editor = name + ':editor'
                subprocess.run(base + ['send-keys', '-t', editor, ':edit sample.txt', 'Enter'],
                               check=True, env=environment)
                time.sleep(.3)
                subprocess.run(base + ['send-keys', '-t', editor, ':wq', 'Enter'],
                               check=True, env=environment)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    result = subprocess.run(base + ['list-windows', '-t', name, '-F', '#{window_name}'],
                                            capture_output=True, text=True, env=environment)
                    if 'editor' not in result.stdout.splitlines():
                        self.fail('Neovim exit removed the editor window instead of revealing a shell')
                    command = subprocess.check_output(base + ['display-message', '-p', '-t', editor,
                                                              '#{pane_current_command}'], text=True,
                                                      env=environment).strip()
                    screen = subprocess.check_output(base + ['capture-pane', '-p', '-t', editor],
                                                     text=True, env=environment)
                    if command in ('bash', 'thin-shell') and screen.rstrip().endswith('$'):
                        break
                    time.sleep(.05)
                else:
                    self.fail('Editor window did not return to a shell')
                marker = project / 'shell-returned'
                subprocess.run(base + ['send-keys', '-t', editor,
                                       'printf ready > ' + str(marker), 'Enter'], check=True,
                               env=environment)
                deadline = time.monotonic() + 5
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(marker.exists(), 'Editor shell did not accept a command')
            finally:
                if base:
                    subprocess.run(base + ['kill-server'], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, env=environment)
                if keeper.poll() is None:
                    keeper.terminate()
                keeper.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
