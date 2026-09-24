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
    # A legacy skills-only directory is not an installed host launcher. The
    # standalone installer must create the runtime without touching the skills.
    skills = home / '.local/share/hpc-workspace/skills/personal'
    skills.mkdir(parents=True)
    (skills / 'SKILL.md').write_text('Existing local skill; preserve it.\n')
    assert not (home / '.local/share/hpc-workspace/runtime').exists()
    original = '# Existing personal startup settings\nexport PERSONAL_SETTING=kept\n'
    (home / '.bashrc').write_text(original)
    login_original = '# Existing login settings; does not source .bashrc\nexport LOGIN_PERSONAL=kept\n'
    (home / '.bash_profile').write_text(login_original)
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
    assert (prefix / 'activate.sh').is_file() and (prefix / 'bin/ws').is_file()
    assert (skills / 'SKILL.md').read_text() == 'Existing local skill; preserve it.\n'
    first = (home / '.bashrc').read_text()
    first_login = (home / '.bash_profile').read_text()
    run([sys.executable, str(installer), str(manifest)])
    assert (home / '.bashrc').read_text() == first
    assert first.startswith(original)
    assert first.count('# >>> hpc-workspace managed PATH >>>') == 1
    assert first_login.startswith(login_original)
    assert first_login.count('# >>> hpc-workspace managed PATH >>>') == 1
    assert (home / '.bash_profile').read_text() == first_login
    run(['/bin/bash', '--noprofile', '--norc', '-c',
         '. "$1"; test "$(command -v ws)" = "$2"', 'test', str(prefix / 'activate.sh'), str(prefix / 'bin/ws')])
    for arguments in (['--noprofile', '-ic'], ['-lic']):
        run(['/bin/bash'] + arguments + [
            'test "$(command -v ws)" = "$1" && ws --help >/dev/null', 'test', str(prefix / 'bin/ws')])
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
    after_update = (home / '.bashrc').read_text()
    assert after_update.startswith(original)
    assert after_update.count('# >>> hpc-workspace managed PATH >>>') == 1
    assert (home / '.bash_profile').read_text() == first_login
    for arguments in (['--noprofile', '-ic'], ['-lic']):
        run(['/bin/bash'] + arguments + [
            'test "$(command -v ws)" = "$1" && ws --help >/dev/null', 'test', str(prefix / 'bin/ws')])
    assert (personal / 'bashrc').read_text() == 'export WORKSPACE_PERSONAL=kept\n'
    print('PASS: actual transferred bundle installs and reinstalls; fresh Bash login and terminal shells find ws without activation; entry and in-shell update preserve personal settings and future startup.')

    custom_home = root / 'site-home'
    custom_home.mkdir()
    paths = [custom_home / '.site/startup.sh', custom_home / '.site/login.sh']
    ordinary = {'.bashrc': '. "$HOME/.site/startup.sh"\n',
                '.bash_profile': '. "$HOME/.site/login.sh"\n'}
    for name, contents in ordinary.items():
        (custom_home / name).write_text(contents)
    env.update(HOME=str(custom_home), WS_CONFIG_DIR=str(custom_home / '.config/hpc-workspace'))
    run([sys.executable, str(installer), str(manifest),
         '--shell-startup', str(paths[0]), '--shell-startup', str(paths[1])])
    prefix = custom_home / '.local/share/hpc-workspace/runtime'
    paths[0].write_text('# Site-specific personal settings retained\n')
    run([str(prefix / 'bin/ws'), 'enter', '--', 'ws', 'update', str(manifest)])
    assert paths[0].read_text().startswith('# Site-specific personal settings retained\n')
    for path in paths:
        assert path.read_text().count('# >>> hpc-workspace managed PATH >>>') == 1
    for name, contents in ordinary.items():
        assert (custom_home / name).read_text() == contents
    for arguments in (['--noprofile', '-ic'], ['-lic']):
        run(['/bin/bash'] + arguments + [
            'test "$(command -v ws)" = "$1" && ws --help >/dev/null', 'test', str(prefix / 'bin/ws')])
    print('PASS: custom site-loaded startup files work for fresh shells and remain selected during an update from inside the workspace; ordinary startup files are unchanged.')
