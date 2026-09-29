"""Capture blocked tasks without touching their files, credentials, or lifetime."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import session_diagnostics as diagnostics


def process_stat(pid, name='tmux: client', state='D', start='123', ticks=20):
    values = [state] + ['0'] * 21
    values[1], values[11], values[17], values[19] = '80', str(ticks), '1', start
    return '{} ({}) {}\n'.format(pid, name, ' '.join(values))


class SessionDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.proc, self.sysfs = self.root / 'proc', self.root / 'sys'
        self.proc.mkdir()
        self.sysfs.mkdir()
        self.write(self.proc / 'self/mountinfo', '')

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def task(self, pid, state='D', name='tmux: client'):
        directory = self.proc / str(pid)
        uid = os.getuid()
        self.write(directory / 'stat', process_stat(pid, name, state))
        self.write(directory / 'status', 'Uid:\t{0}\t{0}\t{0}\t{0}\nCpus_allowed_list:\t0-383\n'.format(uid))
        self.write(directory / 'wchan', 'request_wait_answer\n' if state == 'D' else 'ep_poll\n')
        self.write(directory / 'cgroup', '0::/user.slice/build\n')
        self.write(directory / 'mountinfo', '1 0 0:90 / /workspace-tools rw - fuse.squashfuse SECRET_SOURCE rw,SECRET_OPTION\n')
        thread = directory / 'task' / str(pid)
        self.write(thread / 'stat', process_stat(pid, name, state))
        self.write(thread / 'wchan', 'request_wait_answer\n')
        self.write(thread / 'stack', '[<0>] request_wait_answer+0x1/0x2\n')
        self.write(directory / 'environ', 'API_KEY=SECRET_ENVIRONMENT')
        self.write(directory / 'cmdline', 'codex --key SECRET_ARGUMENT')
        (directory / 'cwd').symlink_to('/unavailable/shared/project')
        return directory

    def test_captures_blocked_client_and_sleeping_server_without_reading_secrets(self):
        self.task(91)
        self.task(80, 'S', 'tmux: server')
        original = diagnostics.read
        def guarded(path, *args):
            self.assertNotIn(Path(path).name, ('environ', 'cmdline', 'abort'))
            return original(path, *args)
        with patch.object(diagnostics, 'read', side_effect=guarded):
            result = diagnostics.sample(self.proc, self.sysfs)
        client = next(row for row in result['processes'] if row['pid'] == 91)
        self.assertEqual(client['details']['blocked_threads'][0]['wchan'], 'request_wait_answer')
        self.assertEqual(client['details']['cwd'], '/unavailable/shared/project')
        self.assertEqual(client['details']['mounts'][0]['type'], 'fuse.squashfuse')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_finds_blocked_worker_thread_when_process_leader_is_sleeping(self):
        directory = self.task(91, 'S', 'codex')
        self.write(directory / 'task/92/stat', process_stat(92, 'codex-worker'))
        self.write(directory / 'task/92/wchan', 'fuse_simple_request')
        result = diagnostics.sample(self.proc, self.sysfs)
        blocked = result['processes'][0]['details']['blocked_threads']
        self.assertEqual(blocked[0]['tid'], 92)
        self.assertIsNotNone(blocked[0]['stack_error'])

    def test_summary_includes_wait_evidence_without_fuse_abort_or_mount_secrets(self):
        self.task(91)
        self.write(self.sysfs / 'fs/fuse/connections/90/waiting', '3\n')
        self.write(self.sysfs / 'fs/fuse/connections/90/abort', 'SECRET_ABORT')
        observed = diagnostics.sample(self.proc, self.sysfs)
        report = dict(samples=[observed], hostname='test-node', uid=os.getuid(), clock_ticks=100,
                      incomplete=False, worker_still_blocked=None, worker_error='')
        text = diagnostics.summary(report)
        self.assertIn('request_wait_answer', text)
        self.assertIn('fuse.squashfuse', text)
        self.assertIn('waiting=3', text)
        self.assertIn('alone is not a deadlock diagnosis', text)
        self.assertNotIn('SECRET', text + json.dumps(observed))

    def test_v1_and_v2_include_parent_quota_when_child_is_unlimited(self):
        for controllers, kind, suffix in [('', 'cgroup2', 'rw'), ('cpu,cpuacct', 'cgroup', 'rw,cpu,cpuacct')]:
            mount_rows = diagnostics.mounts('1 0 0:1 / /sys/fs/cgroup/cpu rw - {} none {}\n'.format(kind, suffix))
            directories = diagnostics.cpu_directories('0:{}:/user.slice/build\n'.format(controllers), mount_rows)
            self.assertEqual(directories, ['/sys/fs/cgroup/cpu', '/sys/fs/cgroup/cpu/user.slice',
                                           '/sys/fs/cgroup/cpu/user.slice/build'])

    def test_mount_root_and_escaped_paths_are_resolved_without_filesystem_traversal(self):
        mount_rows = diagnostics.mounts('1 0 0:1 /user.slice /sys/cpu\\040quota rw - cgroup2 none rw\n')
        self.assertEqual(diagnostics.cpu_directories('0::/user.slice/build\n', mount_rows),
                         ['/sys/cpu quota', '/sys/cpu quota/build'])
        self.assertEqual(diagnostics.cpu_directories('0::/other\n', mount_rows), [])

    def test_stat_handles_parentheses_and_refuses_combining_reused_pids(self):
        self.assertEqual(diagnostics.stat(process_stat(91, 'tmux ) client'))['name'], 'tmux ) client')
        self.task(91)
        original = diagnostics.detail
        def replaced(proc, row):
            result = original(proc, row)
            self.write(self.proc / '91/stat', process_stat(91, start='999'))
            return result
        with patch.object(diagnostics, 'detail', side_effect=replaced):
            self.assertFalse(diagnostics.sample(self.proc, self.sysfs)['processes'][0]['identity_verified'])

    def test_timeout_preserves_partial_sample_and_does_not_signal_unrelated_process(self):
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(lambda: sentinel.poll() is None and sentinel.kill())
        code = 'import json,time; print(json.dumps({"processes": []}), flush=True); time.sleep(30)'
        result = diagnostics.collect([sys.executable, '-c', code], 0.3)
        self.assertTrue(result['incomplete'])
        self.assertEqual(result['samples'], [{'processes': []}])
        self.assertIsNone(result['worker_still_blocked'])
        self.assertIsNone(sentinel.poll())
        sentinel.terminate()
        sentinel.wait(timeout=2)

    def test_report_is_private_and_existing_file_is_preserved(self):
        path = self.root / 'report.json'
        report = dict(samples=[], incomplete=False, worker_still_blocked=None, worker_error='')
        with patch.object(sys, 'platform', 'linux'), patch.object(diagnostics, 'collect', return_value=report), \
                patch.dict(os.environ, {'WS_CONTAINER': '', 'WS_LAYOUT': ''}), patch('builtins.print'):
            self.assertEqual(diagnostics.main(['--output', str(path)]), 0)
            original = path.read_bytes()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(diagnostics.main(['--output', str(path)]), 2)
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
