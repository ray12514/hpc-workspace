"""A real inner Apptainer container reaches synthetic outer-host clients."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/src/lib')
from scheduler import Scheduler
from job_bridge import HostJobs
from test_scheduler import Fixture

runtime = ['apptainer', 'exec', '--cleanenv', '--no-eval', '--no-mount', 'home,cwd,hostfs']
if sys.argv[1] == 'unsquash':
    runtime.append('--unsquash')
runtime += ['--bind', '/home/node:/home/node', '--bind', '/workspace-state:/workspace-state',
            '--bind', '/project:/project', '--pwd', '/project']
entry = ['/input/workspace.sif', '/opt/workspace/bin/container-entry']
subprocess.run(runtime + entry + ['container-smoke'], check=True, timeout=240)
personal = Path('/home/node/.config/hpc-workspace')
(personal / 'nvim.lua').write_text("vim.g.workspace_sif_preference = 'preserved'\n")
dotfile_check = '''
import os
from pathlib import Path
import subprocess
personal = Path.home() / '.config/hpc-workspace'
assert Path(os.environ['XDG_CONFIG_HOME']) == personal / 'xdg'
assert os.access(os.environ['XDG_CONFIG_HOME'], os.W_OK)
assert (personal / 'inputrc').is_file()
assert (personal / 'nvim.lua').read_text() == "vim.g.workspace_sif_preference = 'preserved'\\n"
subprocess.run(['nvim', '--headless',
                "+lua if vim.g.workspace_sif_preference ~= 'preserved' then vim.cmd('cquit 1') end",
                '+qa'], check=True, timeout=30)
print('SIF dotfiles passed: writable app configuration and personal Neovim settings survive re-entry.')
'''
subprocess.run(runtime + entry + ['python3', '-c', dotfile_check], check=True, timeout=240)

fixture = Fixture()
fixture.setUp()
try:
    for site, kind, native in (('ruth', 'pbs', 'qsub'), ('jean', 'slurm', 'sbatch')):
        scheduler = Scheduler(dict(site=site, scheduler=kind), fixture.environment, roots=[fixture.project])
        with HostJobs(scheduler) as host:
            command = runtime + ['--bind', str(host.directory) + ':/workspace-host',
                                 '--bind', str(fixture.project) + ':' + str(fixture.project),
                                 '--pwd', str(fixture.project)] + entry
            environment = dict(os.environ, APPTAINERENV_WS_HOST_JOBS_SOCKET='/workspace-host/scheduler.sock',
                               APPTAINERENV_WS_SITE=site, APPTAINERENV_WS_INSTALL_SKILLS='0',
                               APPTAINERENV_PROJECT_INPUT='literal$(false);input',
                               APPTAINERENV_OPENAI_API_KEY='synthetic-container-key',
                               APPTAINERENV_LD_LIBRARY_PATH='/container/libraries')
            # Prove that the native client is not available on the image PATH.
            # CLI requests then cross the bind-mounted Unix socket as this UID.
            inner = '''
if command -v qsub || command -v sbatch; then exit 90; fi
ws submit --env PROJECT_INPUT "$1" || exit "$?"
ws jobs
'''
            result = subprocess.run(command + ['bash', '-c', inner, 'check', str(fixture.script)],
                                    env=environment, capture_output=True, text=True, timeout=240)
            assert result.returncode == 0, result.stderr
            assert '12345' in result.stdout, result.stdout
            # The last record is the queue request; repeat a submission with a
            # native error to verify the response travels back through Apptainer.
            fixture.exit_file.write_text('7')
            result = subprocess.run(command + ['ws', 'submit', '--env', 'PROJECT_INPUT', str(fixture.script)],
                                    env=environment, capture_output=True, text=True, timeout=240)
            assert result.returncode == 7, result.stderr
            assert 'native scheduler failure' in result.stderr, result.stderr
            record = json.loads(fixture.record.read_text())
            assert Path(record['argv'][0]).name == native, record['argv']
            assert record['argv'][-1] == str(fixture.script)
            assert record['cwd'] == str(fixture.project)
            assert record['environment']['PATH'] == fixture.environment['PATH']
            assert record['environment']['LD_LIBRARY_PATH'] == '/site/scheduler-libraries'
            assert 'OPENAI_API_KEY' not in record['environment']
            assert record['environment']['PROJECT_INPUT'] == 'literal$(false);input'
            fixture.exit_file.write_text('0')
        assert not host.directory.exists()
        print('SIF host connection passed: ' + kind + ', same UID, paths, environment, queue, native errors, cleanup.')
finally:
    fixture.doCleanups()

# Exercise the complete host -> SIF YAML reader -> saved configuration flow.
# The image is the delivered artifact; all profiles and client data are synthetic.
import hashlib
import shlex
import shutil
import tempfile

with tempfile.TemporaryDirectory(prefix='ws-import-integration-') as temporary:
    root = Path(temporary)
    home = root / 'home'
    home.mkdir()
    native = root / 'bin'
    native.mkdir()
    apptainer = shutil.which('apptainer')
    wrapper = native / 'apptainer'
    if sys.argv[1] == 'unsquash':
        wrapper.write_text('#!/bin/sh\nif [ "$1" = exec ]; then shift; exec ' + shlex.quote(apptainer) +
                           ' exec --unsquash "$@"; fi\nexec ' + shlex.quote(apptainer) + ' "$@"\n')
        wrapper.chmod(0o755)
    environment = dict(os.environ, HOME=str(home), WS_CONFIG_DIR=str(root / 'configuration'),
                       XDG_STATE_HOME=str(root / 'state'), WS_INSTALL_SKILLS='0',
                       PATH=str(native) + os.pathsep + os.environ['PATH'])
    source = root / 'local profile.yaml'
    original = Path('/src/tests/fixtures/inspector-slurm.yaml').read_text()
    source.write_text(original)
    config = root / 'configuration/config.json'

    def ws(*arguments, expected=0):
        result = subprocess.run([sys.executable, '/src/bin/ws'] + list(arguments), env=environment,
                                cwd='/project', capture_output=True, text=True, timeout=240)
        assert result.returncode == expected, (arguments, result.returncode, result.stdout, result.stderr)
        return result

    ws('init', '--profile', str(source), '--image', '/input/workspace.sif', '--dry-run')
    assert not config.exists()
    ws('init', '--profile', str(source), '--image', '/input/workspace.sif')
    imported = json.loads(config.read_text())
    assert imported['inspector']['facts']['fabric']['userspace'][0]['prefix'] == '/example/libfabric'
    digest = hashlib.sha256()
    with open('/input/workspace.sif', 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    ws('use', '/input/workspace.sif', '--sha256', digest.hexdigest())
    source.unlink()
    result = ws('enter', '--project', '/project', '--', 'bash', '-c',
                'printf "context=%s\\nhome=%s\\n" "$WS_SITE" "$HOME"')
    assert 'context=example-linux' in result.stdout, result.stdout
    assert 'home=' + str(home) + '\n' in result.stdout, result.stdout
    assert (home / '.config/hpc-workspace/xdg/nvim/init.lua').is_file()
    assert config.read_text() == json.dumps(imported, indent=2) + '\n'
    assert json.loads(ws('jobs', '--dry-run').stdout)['argv'][0] == 'squeue'
    source.write_text(original.replace('/example/openmpi', '/example/updated-openmpi').replace('name: slurm', 'name: pbs'))
    before = config.read_bytes()
    ws('refresh', '--dry-run')
    assert config.read_bytes() == before
    ws('refresh')
    assert json.loads(config.read_text())['inspector']['facts']['mpi_providers'][0]['prefix'] == '/example/updated-openmpi'
    assert json.loads(ws('jobs', '--dry-run').stdout)['argv'][0] == 'qstat'
    before = config.read_bytes()
    source.write_text('schema_version: 2\nsystem: {name: example-linux}\n')
    ws('refresh', expected=2)
    assert config.read_bytes() == before
    print('SIF configuration passed: YAML import, preview, saved image, entry without source, PBS/Slurm defaults, refresh, failed-refresh preservation.')
