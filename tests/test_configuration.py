"""Initial import and explicit refresh using synthetic facts and runtime clients."""
import copy
import hashlib
import importlib.util
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
import configuration
from inspector import read_profile, ProfileError


def sample(name='example-linux', scheduler='slurm'):
    return {
        'schema_version': 1, 'system': {'name': name, 'family': 'linux'},
        'system_externals': [{'name': scheduler, 'version': '24.11', 'prefix': '/example/scheduler'}] if scheduler else [],
        'mpi_providers': [{'name': 'openmpi', 'version': '5.0.5', 'prefix': '/example/mpi'}],
        'fabric': {'type': 'infiniband', 'drivers': [], 'userspace': [
            {'name': 'libfabric', 'version': '1.22.0', 'prefix': '/example/libfabric'}]},
        'unused_secret': 'must-not-import',
    }


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ws configuration ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.folder = self.root / 'configuration'
        self.config = self.folder / 'config.json'
        self.image = self.root / 'workspace image.sif'
        self.image.write_bytes(b'synthetic image')
        self.source = self.root / 'Inspector profile.yaml'
        self.source.write_text(json.dumps(sample()))  # JSON is a YAML subset.
        self.calls = self.root / 'import-calls.jsonl'
        native = self.root / 'native'
        native.mkdir()
        runtime = native / 'apptainer'
        runtime.write_text('''#!{python}
import json, os, sys
from pathlib import Path
sys.path.insert(0, {library!r})
from inspector import normalize
if '--bind' not in sys.argv or sys.argv[-1] != '/tmp/ws-profile.yaml':
    print('synthetic runtime')
    sys.exit(0)
snapshot = sys.argv[sys.argv.index('--bind') + 1].split(':')[0]
with open({calls!r}, 'a') as stream:
    stream.write(json.dumps(dict(argv=sys.argv, environment_names=list(os.environ))) + '\\n')
try:
    print(json.dumps(normalize(json.loads(Path(snapshot).read_text()))))
except (ValueError, TypeError) as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(2)
'''.format(python=sys.executable, library=str(ROOT / 'lib'), calls=str(self.calls)))
        runtime.chmod(0o755)
        self.env = dict(HOME=str(self.home), USER='fixture', LOGNAME='fixture', LANG='C.UTF-8',
                        PATH=str(native) + os.pathsep + os.defpath,
                        XDG_STATE_HOME=str(self.root / 'state'), WS_CONFIG_DIR=str(self.folder))

    def cli(self, *args, **environment):
        return subprocess.run([sys.executable, str(ROOT / 'bin/ws')] + list(args),
                              env=dict(self.env, **environment), cwd=str(self.home),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=15)

    def initialize(self, *args):
        result = self.cli('init', '--profile', str(self.source), '--image', str(self.image), *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def select(self):
        result = self.cli('use', str(self.image), '--sha256', hashlib.sha256(self.image.read_bytes()).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_import_is_private_and_retains_only_useful_facts(self):
        self.initialize()
        saved = json.loads(self.config.read_text())
        self.assertEqual(saved['site'], 'example-linux')
        self.assertEqual(saved['inspector']['facts']['fabric']['userspace'][0]['prefix'], '/example/libfabric')
        self.assertNotIn('unused_secret', self.config.read_text())
        self.assertEqual(saved['inspector']['sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o700)
        self.assertIn('--no-eval', json.loads(self.calls.read_text())['argv'])

    def test_startup_and_jobs_reuse_configuration_without_source_or_inspector(self):
        self.initialize()
        self.select()
        self.source.unlink()
        prior = self.config.read_bytes()
        result = self.cli('enter', '--dry-run', WS_INSPECTOR_PROFILE=str(self.source), PATH=os.defpath)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.image), json.loads(result.stdout)['argv'])
        self.assertNotIn('--nv', result.stdout)
        result = self.cli('submit', '--dry-run', str(ROOT / 'examples/jobs/hello.slurm'), PATH=os.defpath)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['argv'][0], 'sbatch')
        self.assertEqual(self.config.read_bytes(), prior)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)
        result = self.cli('enter', '--site', 'jean', '--image', str(self.image), '--dry-run',
                          WS_INSPECTOR_PROFILE=str(self.source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), prior)

    def test_first_entry_imports_once_and_does_not_implicitly_refresh(self):
        result = self.cli('enter', '--image', str(self.image), WS_INSPECTOR_PROFILE=str(self.source))
        if sys.platform != 'linux':
            self.assertEqual(result.returncode, 2)  # Actual entry is Linux-only; setup is still valid.
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
        before = self.config.read_bytes()
        self.source.write_text(json.dumps(sample(scheduler='pbs')))
        result = self.cli('enter', '--image', str(self.image), '--dry-run', WS_INSPECTOR_PROFILE=str(self.source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)
        result = self.cli('jobs', '--dry-run')
        self.assertEqual(json.loads(result.stdout)['argv'][0], 'squeue')

    def test_import_dry_run_changes_no_saved_configuration_or_state(self):
        result = self.cli('enter', '--profile', str(self.source), '--image', str(self.image), '--dry-run',
                          APPTAINERENV_PYTHONPATH='/unwanted', APPTAINER_BIND='/unwanted:/usr')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.config.exists())
        self.assertFalse((self.root / 'state').exists())
        names = json.loads(self.calls.read_text())['environment_names']
        self.assertNotIn('APPTAINERENV_PYTHONPATH', names)
        self.assertNotIn('APPTAINER_BIND', names)

    def test_refresh_preserves_overrides_image_selection_and_state(self):
        self.initialize('--scheduler', 'pbs')
        self.select()
        state = self.root / 'state/hpc-workspace/example-linux'
        selection = (state / 'selection.json').read_bytes()
        (state / 'history').write_text('saved history')
        saved = json.loads(self.config.read_text())
        saved['overrides']['binds'] = [{'source': str(self.home), 'mode': 'ro'}]
        saved['overrides']['scheduler_env'] = ['LOCAL_CLIENT_SETTING']
        self.config.write_text(json.dumps(saved))
        updated = sample()
        updated['mpi_providers'][0]['prefix'] = '/example/new-mpi'
        self.source.write_text(json.dumps(updated))
        preview = self.cli('refresh', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(json.loads(self.config.read_text()), saved)
        self.assertIn('inspector.facts.mpi_providers', json.loads(preview.stdout)['changed_fields'])
        result = self.cli('refresh')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads(self.config.read_text())
        self.assertEqual(after['overrides'], saved['overrides'])
        self.assertEqual(after['inspector']['facts']['mpi_providers'][0]['prefix'], '/example/new-mpi')
        self.assertEqual((state / 'selection.json').read_bytes(), selection)
        self.assertEqual((state / 'history').read_text(), 'saved history')
        self.assertEqual(json.loads(self.cli('jobs', '--dry-run').stdout)['argv'][0], 'qstat')

    def test_invalid_refresh_and_changed_identity_preserve_working_configuration(self):
        self.initialize()
        before = self.config.read_bytes()
        for data in ({'schema_version': 2}, sample('different-system'),
                     dict(sample(), mpi_providers=[{'prefix': 12}]), dict(sample(), schema_version=True)):
            self.source.write_text(json.dumps(data))
            result = self.cli('refresh', '--image', str(self.image))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(self.config.read_bytes(), before)

    def test_absent_or_ambiguous_scheduler_only_blocks_scheduler_operations(self):
        for kind in ('missing', 'both'):
            data = sample(scheduler=None)
            if kind == 'both':
                data['system_externals'] = [{'name': 'pbs'}, {'name': 'slurm'}]
            self.source.write_text(json.dumps(data))
            self.initialize()
            result = self.cli('enter', '--image', str(self.image), '--dry-run')
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.cli('jobs', '--dry-run')
            self.assertEqual(result.returncode, 2)
            self.assertIn('ws init --scheduler', result.stderr)
        result = self.cli('init', '--scheduler', 'slurm')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.cli('jobs', '--dry-run').stdout)['argv'][0], 'squeue')

    def test_no_profile_is_needed_for_core_shell_or_manual_defaults(self):
        result = self.cli('enter', '--image', str(self.image), '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.config.exists())
        result = self.cli('init', '--site', 'ruth')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.cli('jobs', '--dry-run').stdout)['argv'][0], 'qstat')
        result = self.cli('jobs', '--site', 'jean', '--dry-run')
        self.assertEqual(json.loads(result.stdout)['argv'][0], 'squeue')
        self.assertEqual(json.loads(self.config.read_text())['site'], 'ruth')

    def test_missing_scheduler_fact_preserves_an_existing_named_default(self):
        self.assertEqual(self.cli('init', '--site', 'ruth').returncode, 0)
        self.source.write_text(json.dumps(sample('ruth', scheduler=None)))
        self.initialize()
        result = self.cli('jobs', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['argv'][0], 'qstat')

    def test_import_preserves_previously_selected_local_image_and_history(self):
        self.select()
        state = self.root / 'state/hpc-workspace/local'
        (state / 'history').write_text('before profile')
        self.initialize()
        self.assertEqual(json.loads(self.config.read_text())['state_site'], 'local')
        result = self.cli('enter', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(state) + ':/workspace-state:rw', json.loads(result.stdout)['argv'])
        self.assertEqual((state / 'history').read_text(), 'before profile')

    def test_profile_labels_cannot_escape_state_and_site_overrides_are_validated(self):
        self.source.write_text(json.dumps(sample('../../outside')))
        self.initialize()
        key = json.loads(self.config.read_text())['site']
        self.assertRegex(key, r'^system-[0-9a-f]{16}$')
        self.assertEqual(self.cli('enter', '--site', '../outside', '--image', str(self.image), '--dry-run').returncode, 2)

    def test_first_entry_keeps_the_reader_image_when_import_discovers_existing_site_state(self):
        self.select()
        other = self.root / 'other.sif'
        other.write_bytes(b'other selected image')
        result = self.cli('use', '--site', 'ruth', str(other), '--sha256', hashlib.sha256(other.read_bytes()).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.source.write_text(json.dumps(sample('ruth', 'pbs')))
        result = self.cli('enter', '--profile', str(self.source), '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)['argv']
        self.assertIn(str(self.image), plan)
        self.assertNotIn(str(other), plan)
        self.assertIn(str(self.root / 'state/hpc-workspace/ruth') + ':/workspace-state:rw', plan)
        self.assertFalse(self.config.exists())

    def test_doctor_reports_saved_source_and_facts(self):
        self.initialize()
        self.source.unlink()
        result = self.cli('doctor', '--image', str(self.image))
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(record['scheduler'], 'slurm')
        self.assertEqual(record['configuration']['inspector']['source'], str(self.source))
        self.assertEqual(record['configuration']['inspector']['facts']['mpi_providers'][0]['version'], '5.0.5')

    def test_concurrent_configuration_edit_is_not_overwritten(self):
        self.initialize()
        previous = json.loads(self.config.read_text())
        changed = copy.deepcopy(previous)
        changed['overrides']['scheduler'] = 'pbs'
        self.config.write_text(json.dumps(changed))
        with patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(configuration.ConfigurationError, 'changed during import'):
                configuration.write(previous, previous)
        self.assertEqual(json.loads(self.config.read_text()), changed)


@unittest.skipUnless(importlib.util.find_spec('yaml'), 'YAML parser is bundled in the image')
class YAMLTests(unittest.TestCase):
    def test_actual_inspector_yaml_imports_typed_paths_modules_and_node_targets(self):
        data = read_profile(ROOT / 'tests/fixtures/inspector-slurm.yaml')
        self.assertEqual(data['facts']['os']['major'], 9)
        self.assertEqual(data['facts']['os']['glibc'], '2.34')
        self.assertEqual(data['facts']['mpi_providers'][0]['modules'], ['gcc/13', 'openmpi/5.0.5'])
        self.assertIsNone(data['facts']['node_types']['cpu']['gpu'])
        self.assertEqual(data['scheduler_candidates'], ['slurm'])

    def test_unsafe_duplicate_recursive_malformed_and_unsupported_yaml_are_rejected(self):
        cases = ['!!python/object/apply:os.system ["touch /tmp/ws-never-execute"]',
                 'schema_version: 1\nschema_version: 1\nsystem: {name: example}',
                 'schema_version: 1\nsystem: {name: example}\nunused: &loop [*loop]',
                 'schema_version: 2\nsystem: {name: example}',
                 'schema_version: 1\nsystem: {name: [not, a, string]}',
                 'schema_version: 1\nsystem: {name: example}\nmpi_providers: [',
                 'schema_version: 1\nsystem: {name: example}\n---\nsecond: document']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.yaml'
            for content in cases:
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(ProfileError):
                    read_profile(path)


if __name__ == '__main__':
    unittest.main()
