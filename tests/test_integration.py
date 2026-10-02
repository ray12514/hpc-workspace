import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import integration


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def test_coherent_userspace_preserves_image_and_kernel_paths(self):
        for name in ('usr', 'usr/bin', 'etc', 'opt', 'home', 'scratch', 'run', 'var', 'nix', 'dev', 'proc', 'sys'):
            (self.root / name).mkdir(exist_ok=True)
        (self.root / 'bin').symlink_to('usr/bin')
        mounts = integration.host_mounts(self.root)
        by_path = {x['destination']: x for x in mounts}
        self.assertEqual(by_path['/bin']['source'], str(self.root / 'usr/bin'))
        self.assertEqual(by_path['/usr']['mode'], 'ro')
        self.assertEqual(by_path['/scratch']['mode'], 'rw')
        self.assertEqual(by_path['/run']['mode'], 'rw')
        self.assertFalse({'/nix', '/proc', '/dev', '/sys'} & set(by_path))
        (self.root / 'bin').unlink()
        (self.root / 'bin').mkdir()
        split = {x['destination']: x for x in integration.host_mounts(self.root)}
        self.assertEqual(split['/bin']['source'], str(self.root / 'bin'))

    def test_store_conflict_is_explained_instead_of_hidden(self):
        (self.root / 'nix').mkdir()
        (self.root / 'nix/store').mkdir()
        with self.assertRaisesRegex(ValueError, 'conflicts.*nix'):
            integration.host_mounts(self.root)

    def test_extra_binds_cannot_shadow_tools_or_partial_os(self):
        for destination in ('/', '/nix/store', '/workspace-tools', '/usr/local', '/tmp/../lib'):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                integration.validate_extra({'source': str(self.root), 'destination': destination})

    def test_ssh_client_config_snapshot_preserves_includes_with_user_ownership(self):
        system = self.root / 'etc/ssh'
        included = system / 'config.d/50-redhat.conf'
        included.parent.mkdir(parents=True)
        included.write_text('Host fixture\n    GSSAPIAuthentication yes\n')
        external = self.root / 'etc/crypto-policies/back-ends/openssh.config'
        external.parent.mkdir(parents=True)
        external.write_text('Host *\n    ServerAliveInterval 30\n')
        main = system / 'ssh_config'
        main.write_text('Include config.d/*.conf\nInclude {}\n'.format(external))
        insecure = system / 'config.d/insecure.conf'
        insecure.write_text('Host ignored\n')
        insecure.chmod(0o666)
        main.write_text(main.read_text() + 'Include config.d/insecure.conf\n')
        snapshot = self.root / 'snapshot'
        snapshot.mkdir()
        clone = integration.snapshot_ssh_client_config(snapshot, main)
        for original in (main, included, external):
            copy = clone / str(original).lstrip('/')
            self.assertEqual(copy.read_bytes(), original.read_bytes())
            self.assertEqual(copy.stat().st_mode & 0o777, 0o600)
            self.assertEqual(copy.stat().st_uid, os.getuid())
        self.assertFalse((clone / str(insecure).lstrip('/')).exists())
        args = type('Args', (), {'host_jobs': False, 'work': None, 'gpu': 'none',
                                 'command': []})()
        marker = snapshot / 'environment.json'
        marker.write_text('{}')
        with patch.object(integration.platform, 'system', return_value='Linux'), \
                patch.object(integration.platform, 'machine', return_value='x86_64'), \
                patch.object(integration, 'host_mounts', return_value=[]), \
                patch.object(integration.runtime_setup, 'command', return_value=['apptainer']):
            command, _ = integration.plan({'path': '/image.sif'}, self.root, self.root / 'state',
                                           {'binds': []}, args,
                                           lambda src, dest, mode: '{}:{}:{}'.format(src, dest, mode),
                                           environment_file=marker)
        for original in (main, included, external):
            copy = clone / str(original).lstrip('/')
            self.assertIn('{}:{}:ro'.format(copy, original), command)

    def test_snapshot_is_literal_private_and_removed_after_use(self):
        args = type('Args', (), {'site': 'local'})()
        value = 'literal$(false);\nsecret'
        with patch.dict(os.environ, {'TEST_WORKSPACE_SECRET': value}):
            with integration.snapshot(args, self.root) as snapshot:
                self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
                self.assertEqual(json.loads(snapshot.read_text())['environment']['TEST_WORKSPACE_SECRET'], value)
                folder = snapshot.parent
        self.assertFalse(folder.exists())
