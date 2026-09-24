import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from tool_environment import apply_overrides, job_environment


class JobEnvironmentTests(unittest.TestCase):
    def test_job_client_receives_literal_arguments_status_and_clean_environment(self):
        launcher = Path(__file__).resolve().parents[1] / 'bin/ws'
        with tempfile.TemporaryDirectory() as temp:
            command = Path(temp) / 'fake-srun'
            command.write_text('#!' + sys.executable + '\nimport os,sys\n'
                               'assert sys.argv[1:] == ["--pty", "job with spaces", "literal$(false)"]\n'
                               'assert "TMUX" not in os.environ\n'
                               'assert os.environ["SITE_MODULE"] == "kept"\n'
                               'sys.exit(7)\n')
            command.chmod(0o755)
            environment = dict(os.environ, SITE_MODULE='kept', TMUX='/tmp/old-socket,1,0')
            result = subprocess.run([sys.executable, str(launcher), 'job-env', '--', str(command),
                                     '--pty', 'job with spaces', 'literal$(false)'],
                                    env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 7, result.stderr)

    def test_remote_job_keeps_module_changes_without_image_paths_or_tmux_socket(self):
        env = {'PATH': '/site/bin:/usr/bin', 'EDITOR': 'vi', 'LANG': 'en_US.UTF-8',
               'LD_LIBRARY_PATH': '/site/mpi/lib', 'PRIVATE_TOKEN': 'synthetic',
               'WS_INSTALL_ROOT': '/home/example/runtime'}
        apply_overrides(env, {'PATH': '/workspace-tools/bin:' + env['PATH'], 'EDITOR': 'nvim',
                              'INPUTRC': '/workspace-state/inputrc', 'WS_CONTAINER': '1',
                              'WS_LAYOUT': 'thin-v1', 'LANG': 'C.UTF-8'})
        self.assertNotIn('PRIVATE_TOKEN', env['WS_ENV_RESTORE'])
        env.update(PATH='/new/module/bin:' + env['PATH'], LD_LIBRARY_PATH='/new/module/lib',
                   TMUX='/tmp/old-login-node-socket,12,0', TMUX_PANE='%1')
        clean = job_environment(env)
        self.assertEqual(clean['PATH'], '/new/module/bin:/site/bin:/usr/bin')
        self.assertEqual(clean['LD_LIBRARY_PATH'], '/new/module/lib')
        self.assertEqual(clean['EDITOR'], 'vi')
        self.assertEqual(clean['LANG'], 'en_US.UTF-8')
        self.assertEqual(clean['PRIVATE_TOKEN'], 'synthetic')
        self.assertEqual(clean['WS_INSTALL_ROOT'], '/home/example/runtime')
        for key in ('WS_CONTAINER', 'WS_LAYOUT', 'WS_ENV_RESTORE', 'TMUX', 'TMUX_PANE', 'INPUTRC'):
            self.assertNotIn(key, clean)

    def test_explicit_user_choice_survives_and_scoped_overrides_restore_original(self):
        env = {'EDITOR': 'vi'}
        apply_overrides(env, {'EDITOR': 'nvim', 'XDG_STATE_HOME': '/workspace-state/apps'})
        apply_overrides(env, {'XDG_STATE_HOME': '/another/workspace/state'})
        env['EDITOR'] = 'emacs'
        clean = job_environment(env)
        self.assertEqual(clean['EDITOR'], 'emacs')
        self.assertNotIn('XDG_STATE_HOME', clean)
