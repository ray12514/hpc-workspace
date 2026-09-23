"""Seed personal configuration atomically without replacing existing files."""
import os
from pathlib import Path
import tempfile


def initialize(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_dir():
        raise OSError("Workspace configuration templates are missing: " + str(source))
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    for template in sorted(source.rglob("*")):
        if not template.is_file():
            continue
        target = destination / template.relative_to(source)
        if target.exists() or target.is_symlink():
            continue
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".workspace-dotfile-", dir=str(target.parent))
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(template.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            try:
                # A complete file appears at once. Another shell (or the user)
                # creating this path first wins, including a dangling symlink.
                os.link(temporary, str(target))
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary)
