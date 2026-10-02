"""The shared site diagnostic must detect a missing prompt without leaking startup output."""
import importlib.util
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/diagnose-workspace-entry.py'
spec = importlib.util.spec_from_file_location('diagnose_workspace_entry', str(SCRIPT))
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class WorkspaceDiagnosticTests(unittest.TestCase):
    def run_fixture(self, prompt):
        with tempfile.TemporaryDirectory(prefix='ws-diagnostic-') as directory:
            folder = Path(directory)
            rc = folder / 'bashrc'
            rc.write_text((
                "echo PRIVATE_SITE_BANNER\n"
                "_ws_prompt() { _ws_label='ws:fixture login@test-node'; }\n"
                "PROMPT_COMMAND=_ws_prompt\n"
                "WS_RELEASE=0.7.3-preview3 WS_LAYOUT=thin-v1 WS_CONTAINER=1\n")
                + 'PS1={}\n'.format(shlex.quote(prompt)))
            fake_ws = folder / 'ws'
            fake_ws.write_text('#!/bin/sh\nexec /bin/bash --noprofile --rcfile {} -i\n'.format(shlex.quote(str(rc))))
            fake_ws.chmod(0o755)
            with mock.patch.object(diagnostic.shutil, 'which', return_value=str(fake_ws)):
                facts, error = diagnostic.workspace_facts(None, timeout=10)
            self.assertIsNone(error)
            self.assertNotIn('PRIVATE_SITE_BANNER', str(facts))
            return facts

    def test_reports_visible_workspace_prompt(self):
        facts = self.run_fixture('${_ws_label}\\n\\$ ')
        self.assertEqual(facts['visible_label'], 'yes')
        self.assertEqual(facts['prompt_template'], 'workspace')
        self.assertEqual(facts['prompt_hook'], 'present')
        self.assertEqual(facts['release'], '0.7.3-preview3')

    def test_reports_missing_workspace_prompt(self):
        facts = self.run_fixture('SITE> ')
        self.assertEqual(facts['visible_label'], 'no')
        self.assertEqual(facts['prompt_template'], 'other')
        self.assertEqual(facts['prompt_hook'], 'present')


if __name__ == '__main__':
    unittest.main()
