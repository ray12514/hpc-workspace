"""Personal files survive replacement and simultaneous first entry."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from dotfiles import initialize


class DotfilesTests(unittest.TestCase):
    def test_reentry_preserves_custom_and_linked_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, personal = root / "templates", root / "my settings"
            (source / "xdg/nvim").mkdir(parents=True)
            (source / "xdg/nvim/init.lua").write_text("load the image defaults\n")
            (source / "bashrc").write_text("# starter\n")
            (source / "inputrc").write_text("# starter\n")
            initialize(source, personal)
            self.assertEqual((personal / "xdg/nvim/init.lua").stat().st_mode & 0o777, 0o600)
            (personal / "bashrc").write_text("# my alias\n")
            (personal / "inputrc").unlink()
            (personal / "inputrc").symlink_to(root / "not-yet-present")
            (source / "bashrc").write_text("# new release\n")
            (source / "tmux.conf").write_text("# new tool\n")
            initialize(source, personal)
            self.assertEqual((personal / "bashrc").read_text(), "# my alias\n")
            self.assertTrue((personal / "inputrc").is_symlink())
            self.assertFalse((root / "not-yet-present").exists())
            self.assertEqual((personal / "tmux.conf").read_text(), "# new tool\n")
            self.assertFalse(list(personal.rglob(".workspace-dotfile-*")))

    def test_simultaneous_first_entries_publish_complete_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, personal = root / "templates", root / "personal"
            source.mkdir()
            content = "personal settings\n" * 10000
            (source / "bashrc").write_text(content)
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: initialize(source, personal), range(8)))
            self.assertEqual((personal / "bashrc").read_text(), content)
            self.assertEqual(sorted(p.name for p in personal.iterdir()), ["bashrc"])


if __name__ == "__main__":
    unittest.main()
