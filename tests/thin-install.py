"""Install the actual transferred bundle and enter it without a checkout or --image."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

manifest = Path(sys.argv[1])
release = json.loads(manifest.read_text())
installer = manifest.parent / release['artifacts']['installer']['file']
with tempfile.TemporaryDirectory(prefix='thin-install-') as temporary:
    root = Path(temporary)
    home, project, native = [root / name for name in ('home', 'project', 'bin')]
    for path in (home, project, native):
        path.mkdir()
    original = '# Existing personal startup settings\nexport PERSONAL_SETTING=kept\n'
    (home / '.bashrc').write_text(original)
    personal = home / '.config/hpc-workspace'
    personal.mkdir(parents=True)
    (personal / 'bashrc').write_text('export WORKSPACE_PERSONAL=kept\n')
    (personal / 'nvim.lua').write_text('vim.g.fixture_custom = 789\n')
    apptainer = shutil.which('apptainer')
    (native / 'apptainer').write_text('#!/bin/sh\nif [ "$1" = exec ]; then shift; exec ' + shlex.quote(apptainer) + ' exec --unsquash "$@"; fi\nexec ' + shlex.quote(apptainer) + ' "$@"\n')
    (native / 'apptainer').chmod(0o755)
    env = dict(os.environ, HOME=str(home), PATH=str(native) + ':' + os.environ['PATH'],
               TERM='xterm-256color', WS_CONFIG_DIR=str(personal))
    for key in ('WS_INSTALL_ROOT', 'WS_CONTAINER', 'WS_LAYOUT', 'WS_STATE_HOME', 'WS_SITE'):
        env.pop(key, None)

    def run(command):
        result = subprocess.run(command, cwd=project, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True, timeout=240)
        if result.returncode:
            raise AssertionError((command, result.returncode, result.stdout[-3000:], result.stderr[-6000:]))
        return result.stdout

    run([sys.executable, str(installer), str(manifest)])
    prefix = home / '.local/share/hpc-workspace/runtime'
    assert (prefix / 'current').resolve().name == release['release']
    first = (home / '.bashrc').read_text()
    run([sys.executable, str(installer), str(manifest)])
    assert (home / '.bashrc').read_text() == first
    assert first.startswith(original)
    assert first.count('# >>> hpc-workspace managed PATH >>>') == 1
    run(['/bin/bash', '--noprofile', '--norc', '-c',
         '. "$1"; test "$(command -v ws)" = "$2"', 'test', str(prefix / 'activate.sh'), str(prefix / 'bin/ws')])
    script = r'''
set -e
[[ $WS_LAYOUT == thin-v1 && $WS_RELEASE == "$1" ]]
[[ $WORKSPACE_PERSONAL == kept && $PWD == "$2" && $WS_PROJECT == "$2" ]]
[[ $(command -v bat) == /workspace-tools/bin/bat ]]
[[ $BAT_CONFIG_PATH == "$HOME/.config/hpc-workspace/xdg/bat/config" ]]
printf 'installed release\n' | bat --plain >/dev/null
nvim --headless '+lua assert(vim.g.fixture_custom == 789)' +qa
ws update "$3"
printf 'installed-entry-passed\n'
'''
    output = run([str(prefix / 'bin/ws'), 'enter', '--', 'bash', '--noprofile', '--rcfile',
                  '/workspace-tools/config/bashrc', '-ic', script, 'test', release['release'], str(project), str(manifest)])
    assert 'installed-entry-passed' in output
    assert (home / '.bashrc').read_text() == first
    assert (personal / 'bashrc').read_text() == 'export WORKSPACE_PERSONAL=kept\n'
    print('PASS: actual transferred bundle installs and reinstalls, activates, enters with no site/image arguments, preserves personal settings, and updates from inside the shell.')
