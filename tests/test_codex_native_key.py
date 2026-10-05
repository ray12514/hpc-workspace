"""The optional native Codex helper keeps a saved key out of shell output."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / 'image/config/codex-native-key.bash'
SYNTHETIC = 'synthetic-test-secret'


class CodexNativeKeyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='codex-key-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.environment = dict(os.environ, HOME=str(self.home))
        self.file = self.home / '.config/hpc-workspace/credentials/native-codex.key'
        self.ca_choice = self.file.with_name('native-codex.ca-path')

    def bash(self, command, input=None):
        return subprocess.run(['bash', '--noprofile', '--norc', '-c',
                               'source "$1"; ' + command, 'test', str(HELPER)],
                              input=input, capture_output=True, text=True,
                              env=self.environment, timeout=5)

    def test_hidden_save_and_on_demand_export(self):
        saved = self.bash('ws-codex-key-save', SYNTHETIC + '\n')
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertNotIn(SYNTHETIC, saved.stdout + saved.stderr)
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.file.parent.stat().st_mode & 0o777, 0o700)
        loaded = self.bash('set -x; ws-codex-key-on; set +x; '
                           '[[ $HPC_GATEWAY_KEY == synthetic-test-secret ]] || exit 2; '
                           'ws-codex-key-off; [[ -z ${HPC_GATEWAY_KEY+x} ]]')
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        self.assertNotIn(SYNTHETIC, loaded.stdout + loaded.stderr)

    def test_refuses_world_readable_or_symlinked_key(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text(SYNTHETIC + '\n')
        self.file.chmod(0o644)
        self.assertNotEqual(self.bash('ws-codex-key-on').returncode, 0)
        self.file.chmod(0o600)
        link = self.file.with_name('real-key')
        self.file.rename(link)
        self.file.symlink_to(link)
        self.assertNotEqual(self.bash('ws-codex-key-on').returncode, 0)

    def test_native_launcher_scopes_key_to_agent(self):
        self.assertEqual(self.bash('ws-codex-key-save', SYNTHETIC + '\n').returncode, 0)
        launched = self.bash('''
            export CODEX_CA_CERTIFICATE=/synthetic/site-ca.pem
            ws() {
                [[ $1 == agent && $2 == codex && $3 == --native ]] || return 3
                [[ $HPC_GATEWAY_KEY == synthetic-test-secret ]] || return 4
                [[ $CODEX_CA_CERTIFICATE == /synthetic/site-ca.pem ]] || return 5
            }
            ws-codex-native || exit
            [[ -z ${HPC_GATEWAY_KEY+x} ]]
        ''')
        self.assertEqual(launched.returncode, 0, launched.stderr)
        self.assertNotIn(SYNTHETIC, launched.stdout + launched.stderr)

    def test_setup_scopes_saved_ca_to_native_codex_launch(self):
        certificate = self.home / 'site-ca.pem'
        certificate.write_text('-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n')
        saved = self.bash('ws-codex-native-setup', SYNTHETIC + '\n' + str(certificate) + '\n')
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertNotIn(SYNTHETIC, saved.stdout + saved.stderr)
        self.assertEqual(self.ca_choice.stat().st_mode & 0o777, 0o600)
        launched = self.bash('''
            export CODEX_CA_CERTIFICATE=/wrong/inherited.pem
            ws() {
                [[ $1 == agent && $2 == codex && $3 == --native ]] || return 3
                [[ $HPC_GATEWAY_KEY == synthetic-test-secret ]] || return 4
                [[ $CODEX_CA_CERTIFICATE == "$HOME/site-ca.pem" ]] || return 5
                [[ -z ${CURL_CA_BUNDLE+x} ]] || return 6
            }
            ws-codex-native || exit
            [[ $CODEX_CA_CERTIFICATE == /wrong/inherited.pem ]]
            [[ -z ${HPC_GATEWAY_KEY+x} ]]
        ''')
        self.assertEqual(launched.returncode, 0, launched.stderr)
        reset = self.bash('ws-codex-ca-save', '\n')
        self.assertEqual(reset.returncode, 0, reset.stderr)
        defaults = self.bash('''
            export CODEX_CA_CERTIFICATE=/wrong/inherited.pem
            ws() { [[ -z ${CODEX_CA_CERTIFICATE+x} ]]; }
            ws-codex-native
        ''')
        self.assertEqual(defaults.returncode, 0, defaults.stderr)

    def test_missing_saved_ca_prevents_launch(self):
        certificate = self.home / 'site-ca.pem'
        certificate.write_text('-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n')
        self.assertEqual(self.bash('ws-codex-native-setup', SYNTHETIC + '\n' + str(certificate) + '\n').returncode, 0)
        certificate.unlink()
        result = self.bash('ws() { exit 9; }; ws-codex-native')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unavailable', result.stderr)


if __name__ == '__main__':
    unittest.main()
