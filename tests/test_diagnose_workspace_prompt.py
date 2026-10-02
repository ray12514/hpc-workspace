"""The prompt stage report distinguishes deferred and bypassed site locks."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'diagnose_workspace_prompt', str(ROOT / 'scripts/diagnose-workspace-prompt.py'))
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class PromptStageDiagnosticTests(unittest.TestCase):
    def test_all_startup_boundaries_are_instrumented(self):
        result = diagnostic.instrument_bashrc((ROOT / 'image/config/bashrc').read_text())
        for stage in diagnostic.STAGES:
            self.assertEqual(result.count('_ws_diag_stage ' + stage + '\n'), 1)
        self.assertNotIn('set -x', result)

    def fixture(self, personal_text):
        with tempfile.TemporaryDirectory(prefix='ws-stage-fixture-') as temporary:
            root = Path(temporary)
            home = root / 'home'
            personal = home / '.config/hpc-workspace'
            personal.mkdir(parents=True)
            (personal / 'bashrc').write_text(personal_text)
            (root / 'state').mkdir()
            rcfile = root / 'bashrc'
            rcfile.write_text(diagnostic.instrument_bashrc(
                (ROOT / 'image/config/bashrc').read_text()))
            thin_shell = root / 'thin-shell'
            thin_shell.write_text(diagnostic.instrument_thin_shell(
                (ROOT / 'scripts/thin-shell').read_text().replace(
                    '/workspace-tools/bin/bash', '/bin/bash'), rcfile))
            fake_ws = root / 'ws'
            fake_ws.write_text(
                '#!/bin/sh\nshift\n[ "$1" = "--" ] && shift\n'
                '[ "$1" = "/workspace-tools/bin/bash" ] && shift\n'
                'exec /bin/bash "$@"\n')
            fake_ws.chmod(0o755)
            environment = {'PATH': '/usr/bin:/bin', 'HOME': str(home),
                           'TERM': 'xterm-256color', 'WS_LAYOUT': 'thin-v1',
                           'WS_SITE': 'fixture', 'WS_CONTEXT': 'login',
                           'WS_HOSTNAME': 'test-node',
                           'WS_STATE_HOME': str(root / 'state')}
            with mock.patch.dict(os.environ, environment, clear=True):
                stages, error = diagnostic.capture_stages(str(fake_ws), thin_shell, timeout=10)
            self.assertIsNone(error)
            self.assertEqual(set(stages), set(diagnostic.STAGES))
            return stages

    def test_reports_deferred_readonly(self):
        stages = self.fixture("PROMPT_COMMAND='PS1=SITE'\nreadonly PROMPT_COMMAND\n")
        self.assertEqual(stages['after_personal'][0:2], ['no', 'yes'])
        self.assertEqual(stages['after_final'][0:2], ['yes', 'yes'])

    def test_reports_lock_that_bypasses_deferred_readonly(self):
        stages = self.fixture("PROMPT_COMMAND='PS1=SITE'\nbuiltin readonly PROMPT_COMMAND\n")
        self.assertEqual(stages['after_personal'][0:2], ['yes', 'no'])
        self.assertEqual(stages['after_final'][0:2], ['yes', 'no'])


if __name__ == '__main__':
    unittest.main()
