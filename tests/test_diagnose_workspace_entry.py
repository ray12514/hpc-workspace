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
    def run_fixture(self, prompt, hook='PROMPT_COMMAND=_ws_prompt'):
        with tempfile.TemporaryDirectory(prefix='ws-diagnostic-') as directory:
            folder = Path(directory)
            rc = folder / 'bashrc'
            rc.write_text((
                "echo PRIVATE_SITE_BANNER\n"
                "_ws_prompt() { _ws_label='ws:fixture login@test-node'; }\n"
                + hook + "\n"
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

    def test_restore_hook_alone_is_not_workspace_hook(self):
        facts = self.run_fixture('SITE> ',
                                 hook='PROMPT_COMMAND=(_ws_prompt_restore)')
        self.assertEqual(facts['prompt_hook'], 'missing')

    def test_classifies_readonly_compound_hook_without_exposing_it(self):
        facts = self.run_fixture('SITE> ', hook=(
            "PROMPT_COMMAND='PS1=PRIVATE_SITE_PROMPT; echo PRIVATE_HOOK_VALUE'\n"
            "readonly PROMPT_COMMAND"))
        self.assertEqual(facts['prompt_command'], 'readonly')
        self.assertEqual(facts['prompt_storage'], 'scalar')
        self.assertEqual(facts['prompt_element_count'], '1')
        self.assertEqual(facts['prompt_element_shapes'], 'command')
        self.assertNotIn('PRIVATE_HOOK_VALUE', str(facts))
        self.assertNotIn('PRIVATE_SITE_PROMPT', str(facts))

    def test_classifies_array_function_hook(self):
        facts = self.run_fixture('SITE> ', hook=(
            "site_prompt() { PS1='SITE> '; }\n"
            "PROMPT_COMMAND=(_ws_prompt site_prompt)\n"
            "readonly PROMPT_COMMAND"))
        self.assertEqual(facts['prompt_storage'], 'array')
        self.assertEqual(facts['prompt_element_count'], '2')
        self.assertEqual(facts['prompt_element_shapes'], 'function,function')
        self.assertEqual(facts['prompt_function_references_ps1'], 'yes')


if __name__ == '__main__':
    unittest.main()
