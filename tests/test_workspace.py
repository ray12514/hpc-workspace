"""Check launcher boundaries and release transitions without contacting a cluster."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import workspace


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workspace tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "home"
        self.project = self.root / "project with spaces"
        self.state = self.root / "state"
        self.home.mkdir()
        self.project.mkdir()
        self.image = self.root / "first release.sif"
        self.image.write_bytes(b"test release one")
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("APPTAINER", "SINGULARITY", "SLURM", "PBS"))}
        self.env.update(HOME=str(self.home), XDG_STATE_HOME=str(self.root / "xdg"))
        self.common = ["--site", "ruth", "--state-dir", str(self.state)]

    def run_ws(self, *args, extra_env=None):
        environment = dict(self.env)
        environment.update(extra_env or {})
        return subprocess.run([sys.executable, str(ROOT / "bin/ws")] + list(args),
                              env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)

    def entry(self, *extra, **kwargs):
        return self.run_ws("enter", *self.common, "--image", str(self.image),
                           "--project", str(self.project), "--dry-run", *extra, **kwargs)

    def select(self, image, digest=None):
        return self.run_ws("use", *self.common, str(image), "--sha256",
                           digest or hashlib.sha256(image.read_bytes()).hexdigest())

    def test_dry_run_is_literal_and_does_not_create_state_or_expose_credentials(self):
        literal = "$(touch SHOULD_NOT_EXIST); echo nope"
        result = self.entry("--", "printf", "%s", literal,
                            extra_env={"OPENAI_API_KEY": "test-secret-never-print"})
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["argv"][-3:], ["printf", "%s", literal])
        self.assertIn("--no-eval", plan["argv"])
        self.assertIn("{}:{}:rw".format(self.project, self.project), plan["argv"])
        self.assertIn("OPENAI_API_KEY", plan["forwarded_environment_names"])
        self.assertNotIn("test-secret-never-print", result.stdout + result.stderr)
        self.assertFalse(self.state.exists())

    def test_gpu_requires_the_matching_scheduler_allocation(self):
        result = self.entry("--gpu", "rocm", extra_env={"SLURM_JOB_ID": "other-site"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires an existing allocation", result.stderr)
        result = self.entry("--compute", "--gpu", "rocm", extra_env={"PBS_JOBID": "123.test"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--rocm", json.loads(result.stdout)["argv"])

    def test_clean_environment_preserves_device_masks_and_literals(self):
        args = workspace.parser().parse_args([
            "enter", *self.common, "--image", str(self.image), "--project", str(self.project),
            "--gpu", "cuda", "--dry-run"])
        environment = dict(self.env, PBS_JOBID="123.test", CUDA_VISIBLE_DEVICES="2",
                           APPTAINER_BIND="/host:/usr", APPTAINERENV_LD_LIBRARY_PATH="/host/libs",
                           SINGULARITYENV_PYTHONPATH="/host/python", ANTHROPIC_API_KEY="literal$(date)")
        with patch.dict(os.environ, environment, clear=True):
            command, child = workspace.container_plan(args)
        self.assertIn("--nv", command)
        self.assertNotIn("APPTAINER_BIND", child)
        self.assertNotIn("APPTAINERENV_LD_LIBRARY_PATH", child)
        self.assertNotIn("SINGULARITYENV_PYTHONPATH", child)
        self.assertEqual(child["APPTAINERENV_CUDA_VISIBLE_DEVICES"], "2")
        self.assertEqual(child["APPTAINERENV_ANTHROPIC_API_KEY"], "literal$(date)")

    def test_jobs_use_native_scheduler(self):
        for site, executable in (("ruth", "qstat"), ("jean", "squeue"), ("blueback", "squeue")):
            with self.subTest(site=site):
                result = self.run_ws("jobs", "--site", site, "--dry-run")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["argv"][0], executable)

    def test_select_update_and_rollback_keep_both_images(self):
        second = self.root / "second release.sif"
        second.write_bytes(b"test release two")
        self.assertEqual(self.select(self.image).returncode, 0)
        self.assertEqual(self.select(second).returncode, 0)
        selected = json.loads((self.state / "selection.json").read_text())
        self.assertEqual(selected["current"]["path"], str(second.resolve()))
        self.assertEqual(selected["previous"]["path"], str(self.image.resolve()))
        self.assertEqual(self.select(second).returncode, 0)
        result = self.run_ws("rollback", *self.common)
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = json.loads((self.state / "selection.json").read_text())
        self.assertEqual(selected["current"]["path"], str(self.image.resolve()))
        self.assertTrue(second.is_file())

    def test_bad_checksum_leaves_selection_unchanged(self):
        self.assertEqual(self.select(self.image).returncode, 0)
        before = (self.state / "selection.json").read_bytes()
        result = self.select(self.image, "0" * 64)
        self.assertEqual(result.returncode, 2)
        self.assertIn("checksum mismatch", result.stderr)
        self.assertEqual((self.state / "selection.json").read_bytes(), before)

    def test_modified_image_cannot_be_used_as_a_selected_release(self):
        self.assertEqual(self.select(self.image).returncode, 0)
        self.image.write_bytes(b"replaced image")
        result = self.run_ws("enter", *self.common, "--project", str(self.project), "--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Selected image changed", result.stderr)

    def test_rollback_revalidates_previous_image(self):
        second = self.root / "second.sif"
        second.write_bytes(b"test release two")
        self.assertEqual(self.select(self.image).returncode, 0)
        self.assertEqual(self.select(second).returncode, 0)
        self.image.write_bytes(b"changed previous image")
        result = self.run_ws("rollback", *self.common)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Previous image checksum", result.stderr)

    def test_session_cannot_anchor_itself_in_compute_job(self):
        result = self.run_ws("session", *self.common, "--image", str(self.image),
                             "--project", str(self.project), "--dry-run",
                             extra_env={"PBS_JOBID": "123.test"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside a compute allocation", result.stderr)
        self.assertFalse(self.state.exists())

    def test_profile_binds_cannot_replace_core_directories(self):
        args = workspace.parser().parse_args([
            "enter", *self.common, "--image", str(self.image), "--project", str(self.project), "--dry-run"])
        for destination in ("/usr/", "/tmp/../lib", "/opt", "/opt/workspace/bin"):
            with self.subTest(destination=destination):
                data = {"scheduler": "pbs", "binds": [{"source": str(self.project), "destination": destination}]}
                with patch.object(workspace, "profile", return_value=data), patch.dict(os.environ, self.env, clear=True):
                    with self.assertRaisesRegex(workspace.WorkspaceError, "protected image path"):
                        workspace.container_plan(args)


if __name__ == "__main__":
    unittest.main()
