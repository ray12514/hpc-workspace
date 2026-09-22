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
