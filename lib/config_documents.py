"""Small, local configuration transactions; parsing never executes file contents."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile

LIMIT = 4 * 1024 * 1024


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate configuration key')
        result[key] = value
    return result


def parse_json(contents):
    try:
        result = json.loads(contents, object_pairs_hook=json_object)
    except (ValueError, UnicodeError):
        raise ValueError('Invalid JSON configuration; repair it in an editor before continuing')
    if not isinstance(result, dict):
        raise ValueError('Configuration must contain a JSON object')
    return result


def toml_module():
    manifest = Path('/workspace-tools/manifests/toml-path.txt')
    if manifest.is_file():
        import sys
        sys.path.insert(0, manifest.read_text().strip())
    try:
        import tomlkit
        return tomlkit
    except ImportError:
        raise ValueError('TOML forms need the updated workspace image; use ws enter first')


class Document:
    def __init__(self, path, kind='json', private=False):
        self.link = Path(path).expanduser().absolute()
        self.path = self.link.resolve()
        self.kind = kind
        self.private = private
        self.original = self._read()
        if kind == 'json':
            self.data = parse_json(self.original) if self.original is not None else {}
        else:
            try:
                self.data = toml_module().parse(self.original.decode('utf-8')) if self.original else toml_module().document()
            except (ValueError, UnicodeError):
                raise ValueError('Invalid TOML configuration; repair it in an editor before continuing')

    def _read(self):
        if not self.path.exists():
            return None
        info = self.path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Configuration must be a regular file owned by you: ' + str(self.path))
        if self.private and info.st_mode & 0o077:
            raise ValueError('Credential file must have mode 600: ' + str(self.path))
        if info.st_size > LIMIT:
            raise ValueError('Configuration exceeds the 4 MiB limit')
        return self.path.read_bytes()

    def encode(self):
        if self.kind == 'toml':
            contents = toml_module().dumps(self.data)
            toml_module().parse(contents)
        else:
            contents = json.dumps(self.data, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            parse_json(contents)
        return contents.encode('utf-8')

    def unchanged(self):
        return self.link.resolve() == self.path and self._read() == self.original


def private_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat()
    if info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode):
        raise ValueError('Configuration directory must be owned by you')
    return path


@contextmanager
def locked(folder):
    folder = private_directory(folder)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(str(folder / 'config.lock'), flags, 0o600)
    with os.fdopen(fd, 'w') as lock:
        info = os.fstat(lock.fileno())
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
            raise ValueError('Configuration lock must be a regular file owned by you')
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def replace(path, contents):
    private_directory(path.parent)
    fd, temporary = tempfile.mkstemp(prefix='.ws-config-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def commit(documents, folder):
    """Validate snapshots before writing; retain private backups and undo partial writes."""
    records = [(doc, doc.encode()) for doc in documents]
    if len({doc.path for doc, _ in records}) != len(records):
        raise ValueError('Configuration destinations overlap')
    with locked(folder):
        if not all(doc.unchanged() for doc, _ in records):
            raise ValueError('Configuration changed while the form was open; reopen it to keep those edits')
        backups = private_directory(Path(folder) / 'backups')
        changed = [(doc, data) for doc, data in records if doc.original != data]
        for doc, _ in changed:
            if doc.original is not None:
                fd, name = tempfile.mkstemp(prefix=doc.path.name + '.', dir=str(backups))
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(doc.original)
        written = []
        try:
            for doc, data in changed:
                if not doc.unchanged():
                    raise ValueError('Configuration changed before saving; reopen the form')
                replace(doc.path, data)
                written.append((doc, data))
        except BaseException:
            for doc, data in reversed(written):
                if doc.link.resolve() == doc.path and doc.path.read_bytes() == data:
                    if doc.original is None:
                        doc.path.unlink()
                    else:
                        replace(doc.path, doc.original)
            raise
    return [str(doc.path) for doc, _ in changed]
