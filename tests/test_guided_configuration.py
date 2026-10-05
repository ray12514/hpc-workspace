"""Private synthetic configurations; no credentials or external services involved."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import agent_profiles as agents
import guided_configuration
from config_documents import Document, commit, toml_module
import runtime_setup
import workspace


class ConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ws-config-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.folder = self.root / 'configuration'
        self.env = {'HOME': str(self.root), 'WS_CONFIG_DIR': str(self.folder),
                    'PATH': str(self.root / 'empty-bin'), 'CODEX_HOME': str(self.root / 'codex')}
        context = patch.dict(os.environ, self.env, clear=True)
        context.start()
        self.addCleanup(context.stop)

    def profile(self, name='alpha', tool='pi', source='stored', auth='bearer'):
        if tool == 'codex':
            try:
                toml_module()
            except ValueError:
                self.skipTest('TOML parser is tested in the packaged Linux runtime')
        index = agents.catalog()
        native, key = agents.documents(tool, name, index)
        proposed = dict(base_url='https://' + name + '.example.invalid/v1', model='model-' + name,
                        source=source, variable='TEAM_KEY', auth=auth, api='openai-responses')
        agents.candidate(tool, name, native, key, proposed, 'synthetic-' + name)
        index.data['profiles'][tool][name] = {'path': str(native.path), 'credential': str(key.path)}
        commit([native, key, index], self.folder)
        return native.path, key.path

    def test_transaction_preserves_unknown_values_symlink_and_private_backup(self):
        path = self.root / 'real.json'
        path.write_text('{"unrelated": {"value": 4}}\n')
        link = self.root / 'linked.json'
        link.symlink_to(path)
        doc = Document(link)
        doc.data['changed'] = True
        commit([doc], self.folder)
        self.assertTrue(link.is_symlink())
        self.assertEqual(json.loads(path.read_text())['unrelated'], {'value': 4})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        backup = next((self.folder / 'backups').iterdir())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('changed', backup.read_text())

    def test_concurrent_edit_and_symlink_retarget_prevent_write(self):
        path = self.root / 'config.json'
        path.write_text('{}')
        doc = Document(path)
        doc.data['new'] = 1
        path.write_text('{"other_writer": true}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            commit([doc], self.folder)
        self.assertIn('other_writer', path.read_text())
        link = self.root / 'link'
        link.symlink_to(path)
        doc = Document(link)
        link.unlink()
        link.symlink_to(self.root / 'elsewhere.json')
        with self.assertRaisesRegex(ValueError, 'changed'):
            commit([doc], self.folder)
        self.assertFalse((self.root / 'elsewhere.json').exists())

    def test_duplicate_json_and_nonprivate_credentials_are_rejected_without_content(self):
        path = self.root / 'bad.json'
        path.write_text('{"key":"synthetic-secret","key":2}')
        with self.assertRaises(ValueError) as failure:
            Document(path)
        self.assertNotIn('synthetic-secret', str(failure.exception))
        path.write_text('{}')
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, '600'):
            Document(path, private=True)

    def test_partial_write_failure_restores_prior_files(self):
        a = Document(self.root / 'a.json')
        b = Document(self.root / 'b.json')
        a.data = {'one': 1}
        b.data = {'two': 2}
        import config_documents
        original = config_documents.replace
        def fail_second(path, data):
            if path == b.path:
                raise OSError('synthetic failure')
            original(path, data)
        with patch.object(config_documents, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                commit([a, b], self.folder)
        self.assertFalse(a.path.exists())
        self.assertFalse(b.path.exists())

    def test_pi_switch_rotation_and_environment_cleanup(self):
        self.profile('alpha')
        self.profile('beta', auth='api-key')
        base = dict(os.environ, ANTHROPIC_AUTH_TOKEN='wrong', ANTHROPIC_API_KEY='wrong',
                    OPENAI_API_KEY='wrong', SITE_MODULE='keep')
        for name in ('alpha', 'beta'):
            args, env, overlay = agents.launch_profile('pi', ['--print', 'hello'], dict(base, WS_AGENT_PROFILE=name))
            self.assertEqual(args[:4], ['--provider', 'ws-' + name, '--model', 'model-' + name])
            self.assertEqual(env['SITE_MODULE'], 'keep')
            self.assertNotIn('ANTHROPIC_AUTH_TOKEN', env)
            self.assertEqual(env['WS_SELECTED_PI_KEY'], 'synthetic-' + name)
            self.assertIsNone(overlay)
            self.assertNotIn('synthetic-' + name, str(args))
        native, secret = agents.documents('pi', 'alpha', agents.catalog())
        original = native.path.read_bytes()
        agents.candidate('pi', 'alpha', native, secret, agents.values('pi', 'alpha', native, secret), 'rotated-synthetic')
        commit([native, secret], self.folder)
        self.assertEqual(original, native.path.read_bytes())
        self.assertEqual(agents.load_profile('pi', 'alpha')[2], 'rotated-synthetic')
        self.assertEqual(agents.load_profile('pi', 'beta')[2], 'synthetic-beta')

    def test_missing_credential_or_changed_endpoint_does_not_fall_back(self):
        path, secret = self.profile(source='environment')
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            agents.load_profile('pi', 'alpha')
        os.environ['TEAM_KEY'] = 'synthetic-from-env'
        self.assertEqual(agents.load_profile('pi', 'alpha')[2], 'synthetic-from-env')
        data = json.loads(path.read_text())
        data['providers']['ws-alpha']['baseUrl'] = 'https://changed.example.invalid'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'changed'):
            agents.load_profile('pi', 'alpha')

    def test_native_escape_and_defaults(self):
        self.profile()
        index = agents.catalog()
        index.data['defaults']['pi'] = 'alpha'
        commit([index], self.folder)
        self.assertEqual(agents.launch_profile('pi', [], dict(self.env))[0][:2], ['--provider', 'ws-alpha'])
        self.assertIsNone(agents.launch_profile('pi', [], dict(self.env, WS_AGENT_PROFILE='none'))[2])
        with self.assertRaisesRegex(ValueError, 'active'):
            agents.launch_profile('pi', ['--model', 'other'], dict(self.env))

    def test_pi_stored_native_credential_cannot_override_selected_key(self):
        path, secret = self.profile()
        native_auth = path.parent / 'auth.json'
        native_auth.write_text(json.dumps({'ws-alpha': {'type': 'api_key', 'key': 'wrong-key'}}))
        with self.assertRaisesRegex(ValueError, 'stored Pi credential'):
            agents.launch_profile('pi', [], dict(self.env, WS_AGENT_PROFILE='alpha'))
        native_auth.unlink()
        args, env, _ = agents.launch_profile('pi', [], dict(self.env, WS_AGENT_PROFILE='alpha'))
        self.assertEqual(args[:2], ['--provider', 'ws-alpha'])
        self.assertEqual(env['WS_SELECTED_PI_KEY'], 'synthetic-alpha')

    def test_codex_comments_unknown_settings_and_selected_key(self):
        path, secret = self.profile(tool='codex')
        path.write_text('# Keep this comment\n' + path.read_text() + '\n[history]\nmax_bytes = 12345\n')
        native, key = agents.documents('codex', 'alpha', agents.catalog())
        settings = agents.values('codex', 'alpha', native, key)
        settings['model'] = 'updated-model'
        agents.candidate('codex', 'alpha', native, key, settings)
        commit([native, key], self.folder)
        self.assertIn('# Keep this comment', path.read_text())
        self.assertIn('max_bytes = 12345', path.read_text())
        arguments, env, overlay = agents.launch_profile('codex', ['exec', 'hello'], dict(self.env, WS_AGENT_PROFILE='alpha', OPENAI_API_KEY='wrong'))
        self.assertEqual(arguments[:2], ['--profile', 'ws-alpha'])
        self.assertEqual(env['WS_SELECTED_CODEX_KEY'], 'synthetic-alpha')
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('synthetic-alpha', str(arguments))
        self.assertIsNone(overlay)

    def test_codex_ca_follows_selected_gateway_and_is_checked_at_launch(self):
        self.profile(tool='codex')
        self.profile(name='beta', tool='codex')
        ca = self.root / 'gateway-ca.pem'
        ca.write_text('-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n')
        for name, selected in (('alpha', str(ca)), ('beta', '')):
            native, secret = agents.documents('codex', name, agents.catalog())
            settings = agents.values('codex', name, native, secret)
            settings['ca_bundle'] = selected
            agents.candidate('codex', name, native, secret, settings)
            commit([native, secret], self.folder)
        base = dict(self.env, CODEX_CA_CERTIFICATE='/wrong/inherited.pem')
        _, alpha, _ = agents.launch_profile('codex', [], dict(base, WS_AGENT_PROFILE='alpha'))
        _, beta, _ = agents.launch_profile('codex', [], dict(base, WS_AGENT_PROFILE='beta'))
        self.assertEqual(alpha['CODEX_CA_CERTIFICATE'], str(ca))
        self.assertNotIn('CODEX_CA_CERTIFICATE', beta)
        ca.unlink()
        with self.assertRaisesRegex(ValueError, 'not readable'):
            agents.launch_profile('codex', [], dict(base, WS_AGENT_PROFILE='alpha'))

    def test_pi_ca_follows_selected_gateway(self):
        self.profile(name='alpha', tool='pi')
        self.profile(name='beta', tool='pi')
        ca = self.root / 'gateway-ca.pem'
        ca.write_text('-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n')
        for name, selected in (('alpha', str(ca)), ('beta', '')):
            native, secret = agents.documents('pi', name, agents.catalog())
            settings = agents.values('pi', name, native, secret)
            settings['ca_bundle'] = selected
            agents.candidate('pi', name, native, secret, settings)
            commit([native, secret], self.folder)
        base = dict(self.env, NODE_EXTRA_CA_CERTS='/wrong/inherited.pem')
        _, alpha, _ = agents.launch_profile('pi', [], dict(base, WS_AGENT_PROFILE='alpha'))
        _, beta, _ = agents.launch_profile('pi', [], dict(base, WS_AGENT_PROFILE='beta'))
        self.assertEqual(alpha['NODE_EXTRA_CA_CERTS'], str(ca))
        self.assertNotIn('NODE_EXTRA_CA_CERTS', beta)
        ca.unlink()
        with self.assertRaisesRegex(ValueError, 'not readable'):
            agents.launch_profile('pi', [], dict(base, WS_AGENT_PROFILE='alpha'))

    def test_runtime_saved_path_no_daily_probe_and_explicit_precedence(self):
        binary = self.root / 'apptainer'
        binary.write_text('#!/bin/sh\nexit 0\n')
        binary.chmod(0o755)
        with patch.object(runtime_setup, 'probe', return_value=True) as probe:
            runtime_setup.setup(self.root / 'image.sif', path=str(binary))
            self.assertEqual(probe.call_count, 1)
        with patch.object(runtime_setup, 'probe', side_effect=AssertionError('daily probe')):
            self.assertEqual(runtime_setup.command(), [str(binary)])
        os.environ['WS_APPTAINER'] = '/bin/sh'
        self.assertEqual(runtime_setup.command(), ['/bin/sh'])
        del os.environ['WS_APPTAINER']
        binary.unlink()
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            runtime_setup.command()

    def test_runtime_module_setup_is_scoped_and_arguments_are_literal(self):
        binary = self.root / 'runtime'
        binary.write_text('#!/bin/sh\ntest "$NEEDS_MODULE" = ready || exit 9\nexit 0\n')
        binary.chmod(0o755)
        init = self.root / 'modules.sh'
        init.write_text('module() { test "$1" = load && test "$2" = "apptainer/site" && export NEEDS_MODULE=ready; }\n')
        runtime_setup.setup(self.root / 'image.sif', path=str(binary), module='apptainer/site', module_init=str(init))
        command = runtime_setup.command()
        self.assertIn(str(init), command)
        self.assertEqual(subprocess.call(command + ['literal $(false)']), 0)
        self.assertNotIn('NEEDS_MODULE', os.environ)

    def test_argument_parser_profile_and_native(self):
        a = workspace.parse_arguments(['agent', 'codex', 'alpha', '--', 'exec', 'hello'])
        self.assertEqual(a.name, 'alpha')
        self.assertEqual(a.command, ['exec', 'hello'])
        b = workspace.parse_arguments(['agent', 'pi', '--native', '--', '--version'])
        self.assertTrue(b.native)
        self.assertTrue(workspace.parse_arguments(['agent', 'codex', '--list']).list)

    def test_workspace_form_preserves_saved_facts_and_cancel_leaves_file_unchanged(self):
        document = Document(self.folder / 'config.json')
        document.data = {'schema_version': 1, 'site': 'fixture', 'state_site': 'original',
                         'overrides': {'scheduler_env': ['SITE_MODULE']}, 'personal_note': 'keep'}
        commit([document], self.folder)
        choices = iter(['Add a bind', 'ro', 'Scheduler default', 'slurm', 'Review and save'])
        answers = iter([str(self.root), '/workspace-fixture'])
        class SavedForm:
            def note(self, message):
                pass
            def choose(self, *args):
                return next(choices)
            def text(self, *args, **kwargs):
                return next(answers)
            def confirm(self, message):
                return True
        guided_configuration.workspace_form(SavedForm())
        saved = Document(document.path)
        self.assertEqual(saved.data['personal_note'], 'keep')
        self.assertEqual(saved.data['state_site'], 'original')
        self.assertEqual(saved.data['overrides']['scheduler_env'], ['SITE_MODULE'])
        self.assertEqual(saved.data['overrides']['scheduler'], 'slurm')
        self.assertEqual(saved.data['overrides']['binds'][0]['destination'], '/workspace-fixture')
        class CancelForm(SavedForm):
            def choose(self, *args):
                return 'Review and save'
            def confirm(self, message):
                return False
        guided_configuration.workspace_form(CancelForm())
        self.assertEqual(saved.original, document.path.read_bytes())

    def test_reserved_name_and_unsafe_endpoint_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'reserved'):
            agents.name_check('none')
        for url in ('https://user:key@gateway.invalid', 'https://gateway.invalid?key=value',
                    'http://gateway.invalid', 'https://gateway.invalid:bad'):
            with self.assertRaises(ValueError):
                agents.endpoint_check(url)


if __name__ == '__main__':
    unittest.main()
