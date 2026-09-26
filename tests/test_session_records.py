"""Round-robin login discovery must never treat a remote PID as local."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import session_records
import workspace


class SessionLocationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / 'shared-state'
        self.host = patch('socket.gethostname', return_value='login-two')
        self.host.start()
        self.addCleanup(self.host.stop)
        self.boot = patch('session_records.boot_id', return_value='current-boot')
        self.boot.start()
        self.addCleanup(self.boot.stop)

    def record(self, host, name='ws-example', **extra):
        path = self.state / 'session-hosts' / session_records.host_key(host) / (name + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        data = dict(hostname=host, session=name, pid=123, identity='456',
                    boot_id='current-boot', release='fixture-release', project='/shared/my project')
        data.update(extra)
        path.write_text(json.dumps(data))
        return path

    def test_remote_pid_collision_is_not_checked_or_reported_live(self):
        self.record('login-one')
        with patch('integration.process_identity', return_value='456') as process:
            result = session_records.locations(self.state)
        process.assert_not_called()
        self.assertEqual(result['sessions'][0]['status'], 'recorded')
        self.assertEqual(result['sessions'][0]['hostname'], 'login-one')

    def test_local_ready_starting_and_ended_states(self):
        ready = self.record('login-two').with_suffix('.ready')
        with patch('integration.process_identity', return_value='456'):
            self.assertEqual(session_records.locations(self.state)['sessions'][0]['status'], 'local-starting')
            ready.write_text('{}')
            self.assertEqual(session_records.locations(self.state)['sessions'][0]['status'], 'local-ready')
        with patch('integration.process_identity', return_value=None):
            self.assertEqual(session_records.locations(self.state)['sessions'][0]['status'], 'local-ended')

    def test_old_boot_does_not_reuse_a_matching_pid(self):
        self.record('login-two', boot_id='previous-boot')
        with patch('integration.process_identity', return_value='456') as process:
            self.assertEqual(session_records.locations(self.state)['sessions'][0]['status'], 'local-ended')
        process.assert_not_called()

    def test_old_release_recovers_hostname_and_release_without_rewriting(self):
        path = self.record('login-one', hostname=None, release=None, project=None)
        recipe = self.state / 'integration' / (path.parent.name + '.json')
        recipe.parent.mkdir()
        recipe.write_text(json.dumps({'hostname': 'login-one', 'mounts': ['irrelevant']}))
        path.with_suffix('.ready').write_text(json.dumps({'release': '0.7.1-preview1'}))
        before = {str(file): file.read_bytes() for file in self.state.rglob('*') if file.is_file()}
        row = session_records.locations(self.state)['sessions'][0]
        self.assertEqual(row['hostname'], 'login-one')
        self.assertEqual(row['release'], '0.7.1-preview1')
        self.assertIsNone(row['project'])
        self.assertEqual(before, {str(file): file.read_bytes() for file in self.state.rglob('*') if file.is_file()})

    def test_missing_legacy_metadata_stays_unknown_and_corruption_does_not_hide_others(self):
        self.record('login-one', hostname=None)
        self.record('login-three', name='broken').write_text('{partial')
        report = session_records.locations(self.state)
        self.assertEqual(report['sessions'][0]['status'], 'unknown-node')
        self.assertEqual(len(report['warnings']), 1)

    def test_empty_lookup_needs_no_image_runtime_or_state_creation(self):
        for marker in ({}, {'WS_CONTAINER': '1'}, {'APPTAINER_CONTAINER': '/fake/image.sif'}):
            with self.subTest(marker=marker):
                output = io.StringIO()
                with patch.dict(os.environ, dict(HOME=self.temporary.name, **marker), clear=True), \
                        contextlib.redirect_stdout(output), patch('workspace.selected_image') as image:
                    status = workspace.main(['sessions', '--state-dir', str(self.state), '--json'])
                self.assertEqual(status, 0)
                self.assertEqual(json.loads(output.getvalue())['sessions'], [])
                image.assert_not_called()
                self.assertFalse(self.state.exists())

    def test_display_cannot_emit_terminal_controls_from_metadata(self):
        self.assertEqual(session_records.display('project\n\x1b[31m'), 'project\\n\\u001b[31m')

    def test_inside_lookup_defaults_to_current_workspace_state_with_explicit_overrides(self):
        self.record('login-one')
        environment = dict(HOME=self.temporary.name, WS_CONTAINER='1', WS_SITE='local',
                           WS_STATE_HOME=str(self.state))
        other = Path(self.temporary.name) / 'other-state'
        cases = (([], self.state, 1), (['--state-dir', str(other)], other, 0),
                 (['--site', 'other'], Path(self.temporary.name) / '.local/state/hpc-workspace/other', 0))
        for flags, expected, count in cases:
            with self.subTest(flags=flags), patch.dict(os.environ, environment, clear=True):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    status = workspace.main(['sessions', '--json'] + flags)
                self.assertEqual(status, 0)
                report = json.loads(output.getvalue())
                self.assertEqual(report['state_dir'], str(expected.resolve()))
                self.assertEqual(len(report['sessions']), count)
                if expected != self.state:
                    self.assertFalse(expected.exists())

    def test_new_session_records_location_and_reuses_keeper(self):
        project = Path(self.temporary.name) / 'my project'
        project.mkdir()
        image = {'path': '/images/fixture.sif', 'release': 'fixture-release'}
        args = workspace.parse_arguments(['session', '--site', 'local', '--state-dir', str(self.state),
                                          '--project', str(project), '--detach'])

        def start(command, **kwargs):
            Path(command[-1]).write_text(json.dumps({'release': image['release']}))
            return Mock(pid=123)

        output = io.StringIO()
        with patch('subprocess.Popen', side_effect=start) as process, \
                patch('integration.process_identity', return_value='456'), contextlib.redirect_stdout(output):
            self.assertEqual(workspace.thin_session(args, image), 0)
            self.assertEqual(workspace.thin_session(args, image), 0)
        self.assertEqual(process.call_count, 1)
        record_path = next((self.state / 'session-hosts').glob('*/*.json'))
        record = json.loads(record_path.read_text())
        self.assertEqual(record['hostname'], 'login-two')
        self.assertEqual(record['project'], str(project.resolve()))
        self.assertEqual(record['release'], image['release'])
        self.assertEqual(record['site'], 'local')
        self.assertTrue(record['recorded_at'])
        self.assertEqual(record_path.stat().st_mode & 0o777, 0o600)
        self.assertIn('on login-two', output.getvalue())


if __name__ == '__main__':
    unittest.main()
