"""Synthetic native clients: no cluster, credentials, or real submissions."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
from scheduler import Scheduler
from job_bridge import HostJobs, call


class Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ws scheduler ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project = self.root / 'project with spaces'
        self.project.mkdir()
        self.script = self.project / 'job $(touch UNEXPECTED).sh'
        self.script.write_text('#!/bin/bash\n\necho hello\n')
        self.record = self.root / 'record.json'
        self.exit_file = self.root / 'exit-code'
        self.exit_file.write_text('0')
        native = self.root / 'native'
        native.mkdir()
        source = '''#!{python}
import json, os, sys
from pathlib import Path
Path({record!r}).write_text(json.dumps(dict(argv=sys.argv, cwd=os.getcwd(), environment=dict(os.environ))))
print('12345.test' if Path(sys.argv[0]).name == 'qsub' else 'Submitted batch job 12345')
code = int(Path({exit_file!r}).read_text())
if code: print('native scheduler failure', file=sys.stderr)
sys.exit(code)
'''.format(python=sys.executable, record=str(self.record), exit_file=str(self.exit_file))
        for name in ('qsub', 'sbatch', 'qstat', 'squeue'):
            target = native / name
            target.write_text(source)
            target.chmod(0o755)
        self.environment = {
            'HOME': str(self.root), 'USER': 'test-user', 'LOGNAME': 'test-user',
            'PATH': str(native) + os.pathsep + os.defpath, 'LANG': 'C.UTF-8',
            'LD_LIBRARY_PATH': '/site/scheduler-libraries', 'PBS_CONF_FILE': '/site/pbs.conf',
            'OPENAI_API_KEY': 'synthetic-key-do-not-forward', 'WS_SITE': 'not-a-site',
            'APPTAINERENV_PATH': '/container/bin', 'PROJECT_INPUT': 'literal$(false);input',
        }

    def cli(self, *args, **overrides):
        environment = dict(self.environment, **overrides)
        return subprocess.run([sys.executable, str(ROOT / 'bin/ws')] + list(args),
                              env=environment, cwd=str(self.project),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=15)

    def request(self, **updates):
        request = dict(operation='submit', site='ruth', script=str(self.script),
                       cwd=str(self.project), environment={})
        request.update(updates)
        return request

    def scheduler(self):
        return Scheduler(dict(site='ruth', scheduler='pbs'), self.environment, roots=[self.project])


class SubmissionTests(Fixture):
    def test_native_arguments_cwd_identity_and_selected_environment(self):
        for site, expected in (('ruth', ['-V']), ('jean', ['--export=ALL', '--']),
                               ('blueback', ['--export=ALL', '--'])):
            with self.subTest(site=site):
                result = self.cli('submit', '--site', site, '--env', 'PROJECT_INPUT', str(self.script))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('12345', result.stdout)
                record = json.loads(self.record.read_text())
                self.assertEqual(record['argv'][1:], expected + [str(self.script)])
                self.assertEqual(record['cwd'], str(self.project))
                env = record['environment']
                self.assertEqual(env['USER'], 'test-user')
                self.assertEqual(env['PATH'], self.environment['PATH'])
                self.assertEqual(env['LD_LIBRARY_PATH'], '/site/scheduler-libraries')
                self.assertEqual(env['PROJECT_INPUT'], self.environment['PROJECT_INPUT'])
                for name in ('OPENAI_API_KEY', 'WS_SITE', 'APPTAINERENV_PATH'):
                    self.assertNotIn(name, env)
                self.assertFalse((self.project / 'UNEXPECTED').exists())

    def test_dry_run_does_not_submit_or_print_environment_values(self):
        result = self.cli('submit', '--site', 'ruth', '--dry-run', '--env', 'PROJECT_INPUT', str(self.script))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PROJECT_INPUT', json.loads(result.stdout)['environment_names'])
        self.assertNotIn('literal$(false)', result.stdout)
        self.assertFalse(self.record.exists())

    def test_native_failure_and_stderr_are_preserved(self):
        self.exit_file.write_text('7')
        result = self.cli('submit', '--site', 'jean', str(self.script))
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stderr, 'native scheduler failure\n')

    def test_reject_reserved_environment_and_missing_script_before_client(self):
        for extra in (['--env', 'PATH', str(self.script)], [str(self.project / 'missing.sh')]):
            result = self.cli('submit', '--site', 'ruth', *extra)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.record.exists())

    def test_blocking_directives_after_blank_lines_are_rejected(self):
        for site, directive in (('ruth', '#PBS -I'), ('ruth', '#PBS -W block=true'),
                                ('jean', '#SBATCH --wait'), ('jean', '#SBATCH --get-user-env')):
            self.script.write_text('#!/bin/bash\n\n' + directive + '\necho hello\n')
            result = self.cli('submit', '--site', site, str(self.script))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(self.record.exists())

    def test_resource_directives_are_left_in_the_script(self):
        script = '#!/bin/bash\n\n#SBATCH --time=00:05:00\n#SBATCH --ntasks=1\necho hello\n'
        self.script.write_text(script)
        self.assertEqual(self.cli('submit', '--site', 'jean', str(self.script)).returncode, 0)
        self.assertEqual(self.script.read_text(), script)

    def test_container_cannot_fall_back_to_a_native_client(self):
        result = self.cli('submit', '--site', 'ruth', str(self.script), WS_CONTAINER='1')
        self.assertEqual(result.returncode, 2)
        self.assertIn('No host scheduler connection', result.stderr)
        self.assertFalse(self.record.exists())

    def test_queue_uses_native_client_without_an_image(self):
        for site, native in (('ruth', 'qstat'), ('blueback', 'squeue')):
            result = self.cli('jobs', '--site', site)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(self.record.read_text())
            self.assertEqual(Path(record['argv'][0]).name, native)
            self.assertIn('test-user', record['argv'])


@unittest.skipUnless(hasattr(socket, 'SO_PEERCRED'), 'Linux same-UID transport')
class BridgeTests(Fixture):
    def test_container_cli_uses_host_environment_and_socket_is_removed(self):
        with HostJobs(self.scheduler()) as host:
            connection = str(host.directory / 'scheduler.sock')
            self.assertEqual(host.directory.stat().st_mode & 0o777, 0o700)
            self.assertEqual(Path(connection).stat().st_mode & 0o777, 0o600)
            result = self.cli('submit', '--env', 'PROJECT_INPUT', str(self.script),
                              WS_CONTAINER='1', WS_SITE='ruth', WS_HOST_JOBS_SOCKET=connection,
                              PATH='/container/bin', LD_LIBRARY_PATH='/container/libraries')
            self.assertEqual(result.returncode, 0, result.stderr)
            env = json.loads(self.record.read_text())['environment']
            self.assertEqual(env['PATH'], self.environment['PATH'])
            self.assertEqual(env['LD_LIBRARY_PATH'], self.environment['LD_LIBRARY_PATH'])
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertEqual(env['PROJECT_INPUT'], self.environment['PROJECT_INPUT'])
        self.assertFalse(Path(connection).exists())

    def test_reject_operations_sites_and_symlink_escape_then_still_work(self):
        outside = self.root / 'outside.sh'
        outside.write_text('#!/bin/sh\ntrue\n')
        escape = self.project / 'escape.sh'
        escape.symlink_to(outside)
        with HostJobs(self.scheduler()) as host:
            connection = str(host.directory / 'scheduler.sock')
            for request in (self.request(operation='shell'), self.request(site='blueback'),
                            self.request(script=str(escape)), self.request(cwd=str(self.root)),
                            self.request(environment={'PATH': '/container'})):
                result = call(connection, request)
                self.assertEqual(result['returncode'], 2)
                self.assertFalse(self.record.exists())
            self.assertEqual(call(connection, self.request())['returncode'], 0)

    def test_malformed_request_does_not_kill_server(self):
        with HostJobs(self.scheduler()) as host:
            connection = str(host.directory / 'scheduler.sock')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(connection)
                client.sendall(b'not json\n')
                self.assertIn(b'"returncode": 2', client.recv(65536))
            self.assertEqual(call(connection, self.request(dry_run=True))['returncode'], 0)
            self.assertFalse(self.record.exists())

    def test_busy_bridge_rejects_immediately_instead_of_queueing(self):
        ready = threading.Event()
        release = threading.Event()
        lock = threading.Lock()
        entered = []

        class SlowScheduler:
            def request(self, request):
                with lock:
                    entered.append(request)
                    if len(entered) == 4:
                        ready.set()
                release.wait(10)
                return dict(returncode=0, stdout='', stderr='')

        with HostJobs(SlowScheduler()) as host:
            connection = str(host.directory / 'scheduler.sock')
            clients = [threading.Thread(target=call, args=(connection, {})) for _ in range(4)]
            try:
                for client in clients:
                    client.start()
                self.assertTrue(ready.wait(5))
                result = call(connection, {})
                self.assertEqual(result['returncode'], 2)
                self.assertIn('not submitted', result['stderr'])
                self.assertEqual(len(entered), 4)
            finally:
                release.set()
                for client in clients:
                    client.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
