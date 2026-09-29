"""Existing-workspace controls must never create or select a different keeper."""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import integration
import session_records
import workspace


class SessionControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.state = self.root / 'state'
        self.project = self.root / 'project with spaces'
        self.project.mkdir()
        self.image = self.root / 'original.sif'
        self.image.touch()
        Path(str(self.image) + '.json').write_text(json.dumps(dict(
            schema_version=1, layout='thin-v1', platform='linux/amd64', release='original')))
        for target, value in (('socket.gethostname', 'login-one'),
                              ('session_records.boot_id', 'boot-one'),
                              ('integration.process_identity', '456')):
            mock = patch(target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def record(self, host='login-one', project=None, release='original', ready=True):
        project = project or self.project
        name = integration.session_name('local', project, release)
        path = self.state / 'session-hosts' / session_records.host_key(host) / (name + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(hostname=host, site='local', session=name, pid=123,
                                       identity='456', boot_id='boot-one', project=str(project),
                                       release=release, image=str(self.image))))
        if ready:
            path.with_suffix('.ready').write_text('{}')
        return name, path

    def invoke(self, *arguments):
        output = io.StringIO()
        with patch.dict(os.environ, {'HOME': str(self.root)}, clear=True), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                patch('workspace.enter', return_value=0) as entry:
            status = workspace.main(list(arguments) + ['--state-dir', str(self.state)])
        return status, output.getvalue(), entry

    def test_attach_uses_recorded_image_without_rewriting_or_starting_keeper(self):
        name, record = self.record()
        before = record.read_bytes()
        with patch('workspace.selected_image', side_effect=AssertionError('selected new image')):
            status, output, entry = self.invoke('attach', '--session', name)
        self.assertEqual(status, 0, output)
        args = entry.call_args[0][0]
        self.assertEqual(args.image, str(self.image))
        self.assertEqual(args.project, str(self.project))
        self.assertIn(name, args.command)
        self.assertEqual(record.read_bytes(), before)

    def test_attach_refuses_missing_remote_starting_and_ended_records(self):
        status, output, entry = self.invoke('attach')
        self.assertEqual(status, 2)
        entry.assert_not_called()
        name, path = self.record(host='login-two')
        status, output, entry = self.invoke('attach', '--session', name)
        self.assertEqual(status, 2)
        self.assertIn('login-two', output)
        entry.assert_not_called()
        path.unlink()
        name, path = self.record(ready=False)
        status, output, entry = self.invoke('attach', '--session', name)
        self.assertEqual(status, 2)
        self.assertIn('starting', output)
        entry.assert_not_called()
        with patch('integration.process_identity', return_value=None):
            status, output, entry = self.invoke('attach', '--session', name)
        self.assertEqual(status, 2)
        self.assertIn('ended', output)
        entry.assert_not_called()

    def test_ambiguity_requires_explicit_selection(self):
        name, _ = self.record()
        self.record(release='another-release')
        for flags in ([], ['--project', str(self.project)]):
            status, output, entry = self.invoke('attach', *flags)
            self.assertEqual(status, 2)
            self.assertIn('--session', output)
            entry.assert_not_called()
        status, output, entry = self.invoke('attach', '--session', name, '--detach-others')
        self.assertEqual(status, 0, output)
        self.assertIn('detach-others', entry.call_args[0][0].command)

    def test_stop_requires_selection_and_does_not_enter_an_ended_workspace(self):
        name, path = self.record()
        status, output, entry = self.invoke('stop')
        self.assertEqual(status, 2)
        entry.assert_not_called()
        before = path.read_bytes()
        with patch('integration.process_identity', return_value=None):
            status, output, entry = self.invoke('stop', '--session', name)
        self.assertEqual(status, 0, output)
        self.assertIn('ended', output)
        entry.assert_not_called()
        self.assertEqual(path.read_bytes(), before)

    def test_stop_targets_one_server_and_waits_for_its_keeper(self):
        name, path = self.record()
        other, other_path = self.record(project=self.root / 'other project')
        before = other_path.read_bytes()
        alive = [True]

        def stop(entry):
            self.assertIn(name, entry.command)
            self.assertIn('stop', entry.command)
            self.assertNotIn(other, entry.command)
            self.assertEqual(entry.control_timeout, 60)
            alive[0] = False
            return 0

        args = workspace.parse_arguments(['stop', '--session', name, '--state-dir', str(self.state)])
        args.site = 'local'
        with patch('workspace.enter', side_effect=stop), \
                patch('session_records.keeper_running', side_effect=lambda record: alive[0]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(workspace.control_session(args), 0)
        self.assertEqual(other_path.read_bytes(), before)
        self.assertTrue(path.exists())

    def test_stop_refuses_remote_record_and_reused_pid_from_old_boot(self):
        name, path = self.record(host='login-two')
        status, output, entry = self.invoke('stop', '--session', name)
        self.assertEqual(status, 2)
        entry.assert_not_called()
        path.unlink()
        name, path = self.record()
        record = json.loads(path.read_text())
        record['boot_id'] = 'previous-boot'
        path.write_text(json.dumps(record))
        status, output, entry = self.invoke('stop', '--session', name)
        self.assertEqual(status, 0, output)
        entry.assert_not_called()

    def test_legacy_project_can_be_supplied_but_wrong_identity_is_rejected(self):
        name, path = self.record()
        record = json.loads(path.read_text())
        record.pop('project')
        path.write_text(json.dumps(record))
        status, output, entry = self.invoke('attach', '--session', name, '--project', str(self.project))
        self.assertEqual(status, 0, output)
        self.assertEqual(entry.call_args[0][0].project, str(self.project))
        record['project'] = str(self.root / 'wrong project')
        path.write_text(json.dumps(record))
        status, output, entry = self.invoke('attach', '--session', name)
        self.assertEqual(status, 2)
        entry.assert_not_called()

    def test_control_entry_timeout_stops_only_its_own_process(self):
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(unrelated.wait)
        self.addCleanup(unrelated.terminate)
        started = time.monotonic()
        with self.assertRaisesRegex(workspace.WorkspaceError, 'outcome is unconfirmed'):
            workspace.execute([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.1)
        self.assertLess(time.monotonic() - started, 3)
        self.assertIsNone(unrelated.poll())

    def test_startup_lock_contention_returns_promptly(self):
        name, path = self.record(ready=False)
        args = ['session', '--site', 'local', '--project', str(self.project), '--detach',
                '--state-dir', str(self.state)]
        script = ('import sys; sys.path.insert(0, sys.argv[1]); import workspace; '
                  'workspace.thin_session(workspace.parse_arguments(sys.argv[2:]), '
                  + repr({'path': str(self.image), 'release': 'original'}) + ')')
        # A separate process holds the real filesystem lock used by thin_session.
        # Old code waits forever here instead of reporting an active startup.
        host = subprocess.check_output([sys.executable, '-c',
                                        'import socket; print(socket.gethostname())'],
                                       universal_newlines=True).strip()
        folder = self.state / 'session-hosts' / session_records.host_key(host)
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + '.lock')).open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = subprocess.run([sys.executable, '-c', script, str(ROOT / 'lib')] + args,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, timeout=2)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('startup or stop', result.stderr)
        self.assertFalse((folder / (name + '.json')).exists())


if __name__ == '__main__':
    unittest.main()
