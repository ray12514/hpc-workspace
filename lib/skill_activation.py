"""Make image-bundled skills discoverable from a persistent user home."""
from pathlib import Path
import os
import shutil
import tempfile


def activate(source, home, release):
    """Snapshot shipped skills and link them for Codex; preserve user-owned paths.

    Return paths that were deliberately left alone because they already existed.
    """
    source, home = Path(source), Path(home)
    if not source.is_dir():
        raise FileNotFoundError(source)
    shipped = sorted(item for item in source.iterdir()
                     if item.is_dir() and (item / 'SKILL.md').is_file())
    if not shipped:
        raise ValueError('workspace: bundled skill directory is empty')
    store = home / '.local/share/hpc-workspace/skills'
    snapshot = store / release
    store.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not snapshot.exists():
        stage = Path(tempfile.mkdtemp(prefix='.install-', dir=str(store)))
        try:
            for item in shipped:
                shutil.copytree(item, stage / item.name)
            try:
                stage.rename(snapshot)
            except OSError:
                if not snapshot.is_dir():
                    raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    folder = home / '.agents/skills'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    conflicts = []
    for skill in sorted(snapshot.iterdir()):
        if not skill.is_dir() or not (skill / 'SKILL.md').is_file():
            continue
        link = folder / skill.name
        if link.is_symlink():
            target = link.resolve()
            if target == skill.resolve():
                continue
            try:
                target.relative_to(store.resolve())
            except ValueError:
                pass
            else:
                temporary = folder / ('.' + skill.name + '.' + str(os.getpid()))
                temporary.symlink_to(skill)
                temporary.replace(link)
                continue
        if link.exists() or link.is_symlink():
            conflicts.append(link)
        else:
            try:
                link.symlink_to(skill)
            except FileExistsError:
                pass
    return conflicts
