"""The thin entry activates bundled skills without replacing personal skills."""
from pathlib import Path
import tempfile
import unittest

from skill_activation import activate


class SkillActivationTest(unittest.TestCase):
    def test_install_update_and_preserve_personal_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'bundle'
            for name in ('research', 'codebase-design'):
                folder = source / name
                folder.mkdir(parents=True)
                (folder / 'SKILL.md').write_text(name + '\n')
            home = root / 'home'
            personal = home / '.agents/skills/research'
            personal.mkdir(parents=True)
            (personal / 'SKILL.md').write_text('personal\n')

            conflicts = activate(source, home, 'preview1')
            self.assertEqual(conflicts, [personal])
            self.assertEqual((personal / 'SKILL.md').read_text(), 'personal\n')
            link = home / '.agents/skills/codebase-design'
            self.assertTrue(link.is_symlink())
            self.assertEqual((link / 'SKILL.md').read_text(), 'codebase-design\n')

            (source / 'codebase-design/SKILL.md').write_text('updated\n')
            activate(source, home, 'preview2')
            self.assertEqual((link / 'SKILL.md').read_text(), 'updated\n')
            self.assertEqual((personal / 'SKILL.md').read_text(), 'personal\n')

    def test_unrelated_symlink_and_missing_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home, source, external = (root / item for item in ('home', 'bundle', 'external'))
            source.mkdir()
            external.mkdir()
            (external / 'SKILL.md').write_text('external\n')
            folder = home / '.agents/skills'
            folder.mkdir(parents=True)
            (folder / 'research').symlink_to(external)
            (source / 'research').mkdir()
            (source / 'research/SKILL.md').write_text('shipped\n')
            self.assertEqual(activate(source, home, 'preview1'), [folder / 'research'])
            self.assertEqual((folder / 'research/SKILL.md').read_text(), 'external\n')
            with self.assertRaises(FileNotFoundError):
                activate(root / 'absent', home, 'preview2')


if __name__ == '__main__':
    unittest.main()
