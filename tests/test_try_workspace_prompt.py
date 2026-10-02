"""The trial shell safely points at a private rcfile in the mounted project."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'try_workspace_prompt', str(ROOT / 'scripts/try-workspace-prompt.py'))
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class PromptCandidateTests(unittest.TestCase):
    def test_generated_shell_accepts_spaced_and_quoted_project_path(self):
        source = (ROOT / 'scripts/thin-shell').read_text()
        with tempfile.TemporaryDirectory(prefix='ws prompt candidate ') as temp:
            path = Path(temp) / "project's bashrc"
            script = Path(temp) / 'thin-shell'
            script.write_text(candidate.candidate_shell(source, path))
            subprocess.run(['/bin/bash', '-n', str(script)], check=True)
            self.assertIn('export WS_PROMPT_RC=', script.read_text())
            self.assertNotIn(str(path) + '\n', script.read_text())


if __name__ == '__main__':
    unittest.main()
