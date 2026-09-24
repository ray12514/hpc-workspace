"""Run inside an offline thin fixture, with synthetic hostile library settings."""
import json
import os
from pathlib import Path
import subprocess
import shutil


def run(command, **kwargs):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, timeout=120, **kwargs)
    assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
    assert 'cannot change locale' not in result.stderr, (command, result.stderr)
    return result


assert os.environ.get('LC_TERMINAL') == 'fixture-terminal', 'Terminal metadata is not a locale setting'
versions = json.loads(run(['ws', 'tools', '--json']).stdout)
for name in versions:
    if name in ('bash', 'infocmp', 'tput', 'nvim'):
        continue
    flag = '-V' if name in ('tmux', 'lnav') else '--version'
    result = run([name, flag])
    assert (result.stdout + result.stderr).strip(), name

assert os.environ['LC_ALL'] == 'en_US.UTF-8', 'A valid host locale was unnecessarily replaced'
for name in ('cc', 'gcc', 'g++', 'gfortran', 'clang', 'python3', 'node'):
    path = shutil.which(name)
    assert path is None or not path.startswith('/workspace-tools/'), (name, path)
run(['bash', '--noprofile', '--norc', '-c', '[[ $LC_ALL == en_US.UTF-8 ]]'])
assert 'tar' in run(['tldr', 'tar']).stdout.lower(), 'Offline help is missing'
assert json.loads(run(['yq', '-o=json', '.name'], input='name: workspace\n').stdout) == 'workspace'
assert 'a,2' in run(['mlr', '--csv', 'filter', '$value > 1'], input='name,value\na,2\nb,1\n').stdout
logfile = Path('toolkit-fixture.log')
logfile.write_text('2026-09-24 12:00:00 INFO workspace-needle\n')
assert 'workspace-needle' in run(['lnav', '-n', str(logfile)]).stdout

script = '''import json,os,sys
assert 'WS_CONTAINER' not in os.environ
assert 'TMUX' not in os.environ and 'TMUX_PANE' not in os.environ
assert not any(p.startswith('/workspace-tools') for p in os.environ['PATH'].split(':'))
assert not os.environ.get('SHELL', '').startswith('/workspace-tools')
assert os.environ.get('GIT_PAGER') != 'delta --paging=auto'
assert os.environ['MODULE_SENTINEL'] == 'before'
assert os.environ['LD_LIBRARY_PATH'].endswith('/poison')
assert sys.argv[1:] == ['a script with spaces', 'literal$(false)']
print('job-environment-passed')
'''
assert 'job-environment-passed' in run(['ws', 'job-env', '--', '/usr/bin/python3', '-c', script,
                                      'a script with spaces', 'literal$(false)'],
                                     env=dict(os.environ, TMUX='/tmp/login-socket,12,0', TMUX_PANE='%0')).stdout

result = run(['nvim', '--headless', '-c', 'luafile /src/tests/thin-editor.lua'])
assert 'editor-toolkit-passed' in result.stdout + result.stderr, result.stderr
print('PASS: packaged tool and agent versions, locale preservation, offline help, data tools, job environment and editor integration.')
