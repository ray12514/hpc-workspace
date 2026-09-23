import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import releases


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.prefix = self.home / 'runtime with spaces'
        for target, value in [('platform.system', 'Linux'), ('platform.machine', 'x86_64')]:
            mock = patch('releases.' + target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.dict(os.environ, {'HOME': str(self.home)}, clear=True)
        mock.start()
        self.addCleanup(mock.stop)

    def bundle(self, version, unsafe=False):
        folder = self.root / version
        folder.mkdir()
        image = folder / 'workspace.sif'
        image.write_bytes(('image ' + version).encode())
        source = folder / 'source.tar.gz'
        with tarfile.open(source, 'w:gz') as out:
            for path in ('bin/ws', 'lib/workspace.py'):
                item = tarfile.TarInfo('hpc-workspace/' + path)
                item.size = 1
                out.addfile(item, io.BytesIO(b'#'))
            if unsafe:
                item = tarfile.TarInfo('hpc-workspace/../../outside')
                item.size = 1
                out.addfile(item, io.BytesIO(b'x'))
        data = {'schema_version': 1, 'layout': 'thin-v1', 'platform': 'linux/amd64', 'release': version,
                'artifacts': {role: {'file': p.name, 'sha256': releases.digest(p)}
                              for role, p in [('image', image), ('source', source)]}}
        manifest = folder / 'release.json'
        manifest.write_text(json.dumps(data))
        return manifest

    def test_install_update_rollback_preserve_personal_files_and_hook(self):
        bashrc = self.home / '.bashrc'
        bashrc.write_text('export MY_PERSONAL_SETTING=yes\n')
        one = self.bundle('one')
        releases.install(one, self.prefix)
        initial = bashrc.read_text()
        releases.install(one, self.prefix)
        self.assertEqual(initial, bashrc.read_text())
        two = self.bundle('two')
        releases.install(two, self.prefix)
        self.assertEqual((self.prefix / 'current').resolve().name, 'two')
        releases.rollback(self.prefix)
        self.assertEqual((self.prefix / 'current').resolve().name, 'one')
        self.assertEqual(initial, bashrc.read_text())
        self.assertEqual(initial.count('>>> hpc-workspace'), 1)
        self.assertIn('MY_PERSONAL_SETTING=yes', initial)

    def test_bad_checksum_or_archive_preserves_current(self):
        releases.install(self.bundle('one'), self.prefix, False)
        two = self.bundle('two')
        (two.parent / 'workspace.sif').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            releases.install(two, self.prefix)
        with self.assertRaisesRegex(ValueError, 'unsafe path'):
            releases.install(self.bundle('bad', unsafe=True), self.prefix)
        self.assertEqual((self.prefix / 'current').resolve().name, 'one')
        self.assertFalse((self.prefix / 'releases/bad').exists())
        self.assertFalse(list((self.prefix / 'releases').glob('.install-*')))

    def test_corrupt_rollback_image_does_not_change_selection(self):
        releases.install(self.bundle('one'), self.prefix, False)
        releases.install(self.bundle('two'), self.prefix, False)
        (self.prefix / 'releases/one/image.sif').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            releases.rollback(self.prefix)
        self.assertEqual((self.prefix / 'current').resolve().name, 'two')
