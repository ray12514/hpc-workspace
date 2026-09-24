import argparse
import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import bootstrap
import releases

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workspace setup ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / 'checkout with spaces'
        (self.checkout / 'releases').mkdir(parents=True)
        self.home = self.root / 'home'
        self.home.mkdir()
        env = patch.dict(os.environ, {'HOME': str(self.home), 'WS_INSTALL_ROOT': ''})
        env.start()
        self.addCleanup(env.stop)
        self.args = argparse.Namespace(download_only=True, download_dir=None, prefix=None,
                                       shell_startup=None, no_shell_hook=False)
        self.requests = []
        self.web = self.root / 'web'
        self.web.mkdir()
        self.manifest = self.bundle('0.6.1-preview1')
        self.recommend(self.manifest)

    def bundle(self, version):
        folder = self.web / ('v' + version)
        folder.mkdir()
        image = folder / 'image.sif'
        image.write_bytes(('synthetic image ' + version).encode())
        source = folder / 'source.tar.gz'
        with tarfile.open(str(source), 'w:gz') as archive:
            for name, content in [('bin/ws', 'print("fixture ' + version + '")\n'),
                                  ('lib/workspace.py', '# synthetic workspace\n')]:
                member = tarfile.TarInfo('hpc-workspace/' + name)
                encoded = content.encode()
                member.size = len(encoded)
                archive.addfile(member, io.BytesIO(encoded))
        installer = folder / 'installer.py'
        shutil.copyfile(str(ROOT / 'lib/releases.py'), str(installer))
        record = {'schema_version': 1, 'layout': 'thin-v1', 'platform': 'linux/amd64',
                  'release': version, 'artifacts': {
                      role: {'file': path.name, 'bytes': path.stat().st_size,
                             'sha256': bootstrap.checksum(path)}
                      for role, path in [('image', image), ('source', source), ('installer', installer)]}}
        manifest = folder / ('release-' + version + '.json')
        manifest.write_text(json.dumps(record))
        return manifest

    def recommend(self, manifest):
        (self.checkout / 'releases/recommended.json').write_text(json.dumps({
            'release': json.loads(manifest.read_text())['release'],
            'manifest_sha256': bootstrap.checksum(manifest)}))

    def cache(self):
        return self.checkout / 'dist/downloads/0.6.1-preview1'

    def cached_bundle(self):
        self.cache().parent.mkdir(parents=True)
        shutil.copytree(str(self.manifest.parent), str(self.cache()))

    def run_setup(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return bootstrap.setup(self.args, self.checkout)

    def server(self):
        if not (shutil.which('curl') or shutil.which('wget')):
            self.skipTest('curl or wget needed for actual HTTP download tests')
        web, requests = self.web, self.requests

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                requests.append((self.path, self.headers.get('Range')))
                body = (web / self.path.lstrip('/')).read_bytes()
                offset = int(self.headers.get('Range', 'bytes=0-')[6:-1])
                self.send_response(206 if offset else 200)
                self.send_header('Content-Length', str(len(body) - offset))
                if offset:
                    self.send_header('Content-Range', 'bytes {}-{}/{}'.format(offset, len(body) - 1, len(body)))
                self.end_headers()
                self.wfile.write(body[offset:])

        server = HTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever)
        worker.daemon = True
        worker.start()

        def close():
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()

        self.addCleanup(close)
        url = patch('bootstrap.RELEASE_URL', 'http://127.0.0.1:' + str(server.server_port))
        url.start()
        self.addCleanup(url.stop)

    def test_download_preview_bundle_then_reuse_offline(self):
        self.server()
        self.assertEqual(self.run_setup(), 0)
        self.assertEqual(len(self.requests), 4)
        self.assertEqual(list(self.home.iterdir()), [])
        for original in self.manifest.parent.iterdir():
            self.assertEqual((self.cache() / original.name).read_bytes(), original.read_bytes())
        with patch('bootstrap.download', side_effect=AssertionError('offline')):
            self.assertEqual(self.run_setup(), 0)

    def test_resumes_partial_and_skips_already_complete_downloads(self):
        self.server()
        self.cache().mkdir(parents=True)
        shutil.copyfile(str(self.manifest), str(self.cache() / self.manifest.name))
        (self.cache() / 'image.sif.part').write_bytes((self.manifest.parent / 'image.sif').read_bytes()[:5])
        self.assertEqual(self.run_setup(), 0)
        self.assertIn(('/v0.6.1-preview1/image.sif', 'bytes=5-'), self.requests)
        self.assertEqual(len(self.requests), 3)
        self.assertFalse(list(self.cache().glob('*.part')))

    @unittest.skipUnless(shutil.which('wget'), 'wget fallback')
    def test_wget_download_and_resume_when_curl_is_missing(self):
        self.server()
        self.cache().mkdir(parents=True)
        (self.cache() / 'image.sif.part').write_bytes((self.manifest.parent / 'image.sif').read_bytes()[:5])
        which = shutil.which
        with patch('bootstrap.shutil.which', side_effect=lambda name: None if name == 'curl' else which(name)):
            self.assertEqual(self.run_setup(), 0)
        self.assertIn(('/v0.6.1-preview1/image.sif', 'bytes=5-'), self.requests)

    def test_corrupt_files_never_run_installer_or_change_existing_install(self):
        self.server()
        self.args.download_only = False
        prefix = self.home / 'runtime'
        prefix.mkdir()
        (prefix / 'current').symlink_to('releases/old')
        self.args.prefix = str(prefix)
        for filename in (self.manifest.name, 'image.sif', 'source.tar.gz', 'installer.py'):
            with self.subTest(filename=filename):
                shutil.rmtree(str(self.cache()), ignore_errors=True)
                path = self.manifest.parent / filename
                original = path.read_bytes()
                path.write_bytes(b'corrupt')
                try:
                    with patch('bootstrap.platform.system', return_value='Linux'), \
                            patch('bootstrap.platform.machine', return_value='x86_64'), \
                            patch('bootstrap.subprocess.call') as installer:
                        with self.assertRaisesRegex(ValueError, 'mismatch'):
                            self.run_setup()
                        installer.assert_not_called()
                    self.assertEqual(os.readlink(str(prefix / 'current')), 'releases/old')
                    self.assertFalse((self.home / '.bashrc').exists())
                finally:
                    path.write_bytes(original)

    def test_invalid_manifest_records_are_rejected(self):
        original = json.loads(self.manifest.read_text())
        cases = [('release', 'different'), ('schema_version', 2), ('platform', 'linux/arm64')]
        for key, value in cases:
            with self.subTest(key=key):
                record = dict(original)
                record[key] = value
                self.manifest.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, 'manifest'):
                    bootstrap.verify_manifest(self.manifest, '0.6.1-preview1')
        for name in ('../escape.py', 'image.sif', 'installer.py.part', 'download.lock'):
            with self.subTest(name=name):
                record = json.loads(json.dumps(original))
                record['artifacts']['installer']['file'] = name
                self.manifest.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, 'artifact'):
                    bootstrap.verify_manifest(self.manifest, '0.6.1-preview1')

    def test_unsupported_host_fails_before_downloading(self):
        self.args.download_only = False
        with patch('bootstrap.platform.system', return_value='Darwin'):
            with self.assertRaisesRegex(ValueError, 'download-only'):
                self.run_setup()
        self.assertFalse(self.cache().exists())

    @unittest.skipUnless(platform.system() == 'Linux', 'real Linux standalone installer')
    def test_setup_entrypoint_installs_without_ws_and_is_repeatable(self):
        self.cached_bundle()
        shutil.copyfile(str(ROOT / 'setup'), str(self.checkout / 'setup'))
        (self.checkout / 'lib').mkdir()
        shutil.copyfile(str(ROOT / 'lib/bootstrap.py'), str(self.checkout / 'lib/bootstrap.py'))
        skills = self.home / '.local/share/hpc-workspace/skills/personal.txt'
        skills.parent.mkdir(parents=True)
        skills.write_text('keep\n')
        (self.home / '.bashrc').write_text('# personal\n')
        prefix = self.home / '.local/share/hpc-workspace/runtime'
        env = dict(os.environ, PATH='/usr/bin:/bin')
        for _ in range(2):
            result = subprocess.run([sys.executable, str(self.checkout / 'setup')], cwd=str(self.home),
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((prefix / 'current').resolve().name, '0.6.1-preview1')
            self.assertTrue((prefix / 'activate.sh').is_file())
            self.assertTrue((self.home / '.bashrc').read_text().startswith('# personal\n'))
            self.assertEqual((self.home / '.bashrc').read_text().count('>>> hpc-workspace'), 1)
            self.assertEqual(skills.read_text(), 'keep\n')
            output = subprocess.check_output([str(prefix / 'bin/ws')], env=env, universal_newlines=True)
            self.assertEqual(output.strip(), 'fixture 0.6.1-preview1')

    @unittest.skipUnless(platform.system() == 'Linux', 'real Linux standalone installer')
    def test_upgrade_preserves_custom_prefix_startup_and_rollback(self):
        prefix = self.home / 'custom runtime'
        startup = self.home / '.site/bash config'
        releases.install(self.bundle('0.5.0-preview1'), prefix, startup_files=[str(startup)])
        initial = startup.read_text()
        self.cached_bundle()
        self.args.download_only = False
        with patch.dict(os.environ, {'PATH': str(prefix / 'bin') + os.pathsep + os.environ['PATH']}):
            self.assertEqual(self.run_setup(), 0)
        self.assertEqual((prefix / 'current').resolve().name, '0.6.1-preview1')
        self.assertEqual((prefix / 'previous').resolve().name, '0.5.0-preview1')
        self.assertEqual(startup.read_text(), initial)
        self.assertFalse((self.home / '.bashrc').exists())
        releases.rollback(prefix)
        self.assertEqual((prefix / 'current').resolve().name, '0.5.0-preview1')


if __name__ == '__main__':
    unittest.main()
