"""Exercise real host -> thin SIF -> host clients with public synthetic fixtures."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, '/src/lib')
from integration import process_identity

image = sys.argv[1]
with tempfile.TemporaryDirectory(prefix='thin-fixture-') as temp:
    root = Path(temp)
    home, project, native, state, poison = [root / name for name in ('home', 'project with spaces', 'bin', 'state', 'poison')]
    for path in (home, project, native, state, poison):
        path.mkdir()
    apptainer = shutil.which('apptainer')
    (native / 'apptainer').write_text('#!/bin/sh\nif [ "$1" = exec ]; then shift; exec ' + shlex.quote(apptainer) + ' exec --unsquash "$@"; fi\nexec ' + shlex.quote(apptainer) + ' "$@"\n')
    (native / 'apptainer').chmod(0o755)
    (poison / 'libssl.so.3').write_text('synthetic incompatible module library\n')
    helper = native / 'host-check'
    helper.write_text('''#!/usr/bin/python3
import json,os,sys
print(json.dumps({'argv':sys.argv[1:], 'cwd':os.getcwd(), 'uid':os.getuid(),
 'library':os.environ.get('LD_LIBRARY_PATH'), 'module':os.environ.get('MODULE_SENTINEL'),
 'literal':os.environ.get('PROJECT_INPUT')}))
''')
    helper.chmod(0o755)
    for name in ('sbatch', 'qsub'):
        command = native / name
        command.write_text('#!/bin/sh\n[ "$1" = fail ] && exit 7\nprintf "%s\\n" "$@"\n')
        command.chmod(0o755)
    (project / 'sample.txt').write_text('a needle in shared data\n')
    (home / '.config/hpc-workspace').mkdir(parents=True)
    (home / '.config/hpc-workspace/nvim.lua').write_text('vim.g.fixture_custom = 123\n')
    literal = 'literal$(touch SHOULD_NOT_EXIST); kept'
    env = dict(os.environ, HOME=str(home), TERM='xterm-256color', WS_CONFIG_DIR=str(home / '.config/hpc-workspace'),
               PATH=str(native) + ':' + os.environ['PATH'], PROJECT_INPUT=literal,
               MODULE_SENTINEL='before', LD_LIBRARY_PATH=str(poison),
               TEST_PRIVATE_VALUE='synthetic-private-not-in-plan')
    env['BASH_FUNC_module%%'] = '() { export MODULE_SENTINEL="after"; export LD_LIBRARY_PATH=' + shlex.quote(str(poison)) + '; }'
    common = ['--image', image, '--project', str(project), '--state-dir', str(state)]

    def ws(*args, expected=0):
        result = subprocess.run([sys.executable, '/src/bin/ws'] + list(args), env=env, cwd=project,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=240)
        if result.returncode != expected:
            raise AssertionError((args, result.returncode, result.stdout[-3000:], result.stderr[-6000:]))
        return result

    dry = ws('enter', *common, '--dry-run')
    assert env['TEST_PRIVATE_VALUE'] not in dry.stdout + dry.stderr
    assert not state.exists() or not list(state.iterdir())
    script = r'''
set -e
[[ $(command -v sbatch) == "$1/sbatch" ]]
[[ $(command -v qsub) == "$1/qsub" ]]
[[ $(command -v bash) == /workspace-tools/bin/bash ]]
bind -X | /usr/bin/grep -Eq 'fzf.*history'
module load fixture
[[ $MODULE_SENTINEL == after ]]
bat --plain sample.txt | /usr/bin/grep -q needle
printf 'needle\nother\n' | fzf --filter needle | /usr/bin/grep -q needle
rg needle sample.txt >/dev/null
fd sample . >/dev/null
jq -ne '1+1 == 2' >/dev/null
host-check 'argument with spaces' > native.json
sbatch 'job script.slurm' > scheduler.txt
qsub fail && exit 91 || [[ $? == 7 ]]
printf updated >> sample.txt
nvim --headless '+lua assert(vim.g.fixture_custom == 123); local r=vim.json.decode(vim.fn.system({"host-check","editor child"})); assert(r.module == "after"); assert(r.literal == vim.env.PROJECT_INPUT); vim.fn.writefile({vim.json.encode(r)}, "editor.json")' +qa
printf 'integration-passed\n'
'''
    result = ws('enter', *common, '--', 'bash', '--noprofile', '--rcfile', '/workspace-tools/config/bashrc', '-ic', script, 'test', str(native))
    assert 'integration-passed' in result.stdout
    expected = json.loads((project / 'native.json').read_text())
    assert expected['argv'] == ['argument with spaces']
    assert expected['cwd'] == str(project) and expected['uid'] == os.getuid()
    assert expected['library'] == str(poison) and expected['module'] == 'after' and expected['literal'] == literal
    assert (project / 'sample.txt').read_text().endswith('updated')
    assert (project / 'scheduler.txt').read_text() == 'job script.slurm\n'
    assert not (project / 'SHOULD_NOT_EXIST').exists()
    assert all(env['TEST_PRIVATE_VALUE'] not in p.read_text() for p in (state / 'integration').glob('*.json'))
    print('PASS: native PBS/Slurm argv and status, UID, paths, modules, literal environment, shared files, tool libraries and editor children.', flush=True)

    session = ws('session', *common, '--detach')
    name = re.search(r'Workspace session (ws-[a-z0-9-]+)', session.stdout).group(1)
    again = ws('session', *common, '--detach')
    assert name in again.stdout
    check = r'''
import json,os,shlex,subprocess,sys,time
from pathlib import Path
name=sys.argv[1]; base=['tmux','-L',name]; project=Path.cwd()
try:
    panes=subprocess.check_output(base+['list-panes','-a','-F','#{window_name}|#{pane_dead}'],text=True)
    assert set(panes.splitlines()) == {'workspace|0','editor|0'}, panes
    subprocess.run(base+['send-keys','-t',name+':workspace','printf ready > '+shlex.quote(str(project/'shell-ready')),'Enter'],check=True)
    subprocess.run(base+['send-keys','-t',name+':editor',':lua vim.fn.writefile({"ready"}, "editor-ready")','Enter'],check=True)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline and not all((project/f).exists() for f in ('shell-ready','editor-ready')): time.sleep(.1)
    assert all((project/f).exists() for f in ('shell-ready','editor-ready')), panes
    subprocess.run(base+['send-keys','-t',name+':workspace',
        '{ command -v fzf; fzf --version; } > fzf-resolution; : > fzf-done','Enter'],check=True)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and not (project/'fzf-done').exists(): time.sleep(.1)
    assert (project/'fzf-resolution').read_text().splitlines()[0] == '/workspace-tools/bin/fzf', 'Packaged executables disappeared after detaching the runtime'
    (project/'shell-ready').unlink()
    subprocess.run(base+['send-keys','-t',name+':workspace','C-r'],check=True)
    time.sleep(.3)
    subprocess.run(base+['send-keys','-t',name+':workspace','shell-ready'],check=True)
    time.sleep(.3)
    subprocess.run(base+['send-keys','-t',name+':workspace','Enter'],check=True)
    time.sleep(.2)
    subprocess.run(base+['send-keys','-t',name+':workspace','Enter'],check=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and not (project/'shell-ready').exists(): time.sleep(.1)
    assert (project/'shell-ready').exists(), subprocess.check_output(base+['capture-pane','-p','-S','-40','-t',name+':workspace'],text=True)
    subprocess.run(base+['send-keys','-t',name+':workspace','sleep 60','Enter'],check=True)
    time.sleep(.3)
    subprocess.run(base+['send-keys','-t',name+':workspace','C-c'],check=True)
    subprocess.run(base+['send-keys','-t',name+':workspace','printf interrupted > '+shlex.quote(str(project/'interrupt-ready')),'Enter'],check=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and not (project/'interrupt-ready').exists(): time.sleep(.1)
    assert (project/'interrupt-ready').exists()
finally:
    subprocess.run(base+['kill-server'],check=False)
'''
    ws('enter', *common, '--', '/workspace-tools/libexec/python3', '-I', '-c', check, name)
    deadline = time.monotonic() + 15
    records = list((state / 'session-hosts').glob('*/*.json'))
    while time.monotonic() < deadline and any(process_identity(json.loads(p.read_text())['pid']) for p in records):
        time.sleep(.1)
    assert all(process_identity(json.loads(p.read_text())['pid']) is None for p in records), 'Session keeper did not stop'
    print('PASS: packaged tmux starts without host tmux; both windows accept input, reconnect and Ctrl-R work, Ctrl-C returns to the shell.', flush=True)
    ws('init', '--profile', '/src/tests/fixtures/inspector-slurm.yaml', '--image', image)
    saved = json.loads((home / '.config/hpc-workspace/config.json').read_text())
    assert saved['inspector']['facts']['system']['name'] == 'example-linux'
    print('PASS: optional existing Inspector YAML imports through the thin image.', flush=True)
