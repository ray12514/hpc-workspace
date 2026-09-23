import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
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
        self.root = Path(self.temp.name).resolve()
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

    def test_login_profile_selection_preserves_existing_setup_and_symlinks(self):
        one = self.bundle('one')
        original = 'export LOGIN_PERSONAL=yes\n'
        profile = self.home / '.profile'
        profile.write_text(original)
        releases.install(one, self.prefix)
        self.assertFalse((self.home / '.bash_profile').exists())
        self.assertFalse((self.home / '.bash_login').exists())
        self.assertTrue(profile.read_text().startswith(original))
        before = profile.read_text()
        releases.install(one, self.prefix)
        self.assertEqual(before, profile.read_text())
        for name in ('.bash_login', '.bash_profile'):
            with self.subTest(profile=name):
                target = self.home / (name + '.saved')
                target.write_text(original)
                target.chmod(0o640)
                link = self.home / name
                link.symlink_to(target.name)
                releases.install(one, self.prefix)
                self.assertTrue(link.is_symlink())
                self.assertTrue(target.read_text().startswith(original))
                self.assertEqual(target.stat().st_mode & 0o777, 0o640)
                self.assertEqual(target.read_text().count('>>> hpc-workspace'), 1)
                self.assertEqual(profile.read_text(), before)

    def test_no_shell_hook_leaves_startup_files_untouched(self):
        for name in ('.bashrc', '.bash_profile', '.bash_login', '.profile'):
            (self.home / name).write_text('# personal\n')
        releases.install(self.bundle('one'), self.prefix, False)
        releases.install(self.bundle('two'), self.prefix)
        for path in self.home.glob('.*'):
            self.assertEqual(path.read_text(), '# personal\n')

    def test_custom_startup_paths_are_remembered_without_editing_default_files(self):
        bashrc = self.home / '.bashrc'
        bashrc.write_text('# unchanged\n')
        custom = self.home / '.site/startup file.sh'
        second = self.home / '.site/login.sh'
        releases.install(self.bundle('one'), self.prefix, startup_files=[str(custom), str(second)])
        self.assertEqual(bashrc.read_text(), '# unchanged\n')
        self.assertFalse((self.home / '.bash_profile').exists())
        self.assertTrue(custom.is_file() and second.is_file())
        original = custom.read_text()
        # A later update must restore a removed hook in the saved location,
        # without requiring the path again or falling back to .bashrc.
        custom.write_text('# local addition\n')
        releases.install(self.bundle('two'), self.prefix)
        self.assertTrue(custom.read_text().startswith('# local addition\n'))
        self.assertEqual(custom.read_text().count('>>> hpc-workspace'), 1)
        self.assertEqual(second.read_text(), original)
        self.assertEqual(bashrc.read_text(), '# unchanged\n')
        self.assertFalse((self.home / '.bash_profile').exists())
        saved = json.loads((self.prefix / 'shell-startup.json').read_text())
        self.assertEqual(saved['files'], [str(custom), str(second)])
        self.assertEqual((self.prefix / 'shell-startup.json').stat().st_mode & 0o777, 0o600)

    def test_custom_startup_rejects_directory_and_conflicting_options(self):
        one = self.bundle('one')
        with self.assertRaisesRegex(ValueError, 'not a directory'):
            releases.install(one, self.prefix, startup_files=[str(self.home)])
        self.assertFalse((self.prefix / 'current').exists())
        with self.assertRaisesRegex(ValueError, 'cannot be combined'):
            releases.install(one, self.prefix, False, [str(self.home / '.site.sh')])

    def test_invalid_login_block_does_not_modify_bashrc_or_current(self):
        releases.install(self.bundle('one'), self.prefix)
        bashrc = self.home / '.bashrc'
        initial = bashrc.read_text()
        (self.home / '.bash_profile').write_text('# >>> hpc-workspace managed PATH >>>\n')
        with self.assertRaisesRegex(ValueError, 'Incomplete or duplicate'):
            releases.install(self.bundle('two'), self.prefix)
        self.assertEqual(initial, bashrc.read_text())
        self.assertEqual((self.prefix / 'current').resolve().name, 'one')

    @unittest.skipUnless(shutil.which('bash'), 'Bash startup behavior')
    def test_real_bash_login_and_terminal_find_ws_without_manual_activation(self):
        # Sourcing .bashrc from the login profile must not duplicate PATH, and
        # a login profile which omits .bashrc must still find the launcher.
        profile = self.home / '.bash_profile'
        profile.write_text('. "$HOME/.bashrc"\nexport LOGIN_PERSONAL=yes\n')
        (self.home / '.bashrc').write_text('export TERMINAL_PERSONAL=yes\n')
        one = self.bundle('one')
        check = '''
test "$(command -v ws)" = "$1" || { printf 'launcher found: %s\n' "$(command -v ws)"; exit 11; }
case "$2" in login) test "$LOGIN_PERSONAL" = yes || exit 12;;
terminal) test "$TERMINAL_PERSONAL" = yes || exit 13;; esac
IFS=: read -r -a parts <<< "$PATH"
count=0
for part in "${parts[@]}"; do [[ $part == "$3" ]] && count=$((count+1)); done
test "$count" -eq 1
'''
        bash = shutil.which('bash')
        for linked in (True, False):
            if not linked:
                profile.write_text('export LOGIN_PERSONAL=yes\n')
            releases.install(one, self.prefix)
            for arguments, kind in ((['--noprofile', '-ic'], 'terminal'), (['-lic'], 'login')):
                result = subprocess.run([bash] + arguments + [check, 'test', str(self.prefix / 'bin/ws'), kind, str(self.prefix / 'bin')],
                                        env=dict(os.environ, PATH='/usr/bin:/bin', TERM='dumb'),
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
                self.assertEqual(result.returncode, 0, '{} linked={}: {}'.format(kind, linked, result.stdout + result.stderr))
