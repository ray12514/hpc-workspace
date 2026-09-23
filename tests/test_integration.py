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

    def test_snapshot_is_literal_private_and_removed_after_use(self):
        args = type('Args', (), {'site': 'local'})()
        value = 'literal$(false);\nsecret'
        with patch.dict(os.environ, {'TEST_WORKSPACE_SECRET': value}):
            with integration.snapshot(args, self.root) as snapshot:
                self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
                self.assertEqual(json.loads(snapshot.read_text())['environment']['TEST_WORKSPACE_SECRET'], value)
                folder = snapshot.parent
        self.assertFalse(folder.exists())
