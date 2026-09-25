"""Remember a usable local Apptainer invocation; probe only during explicit setup."""
import datetime
import os
from pathlib import Path
import shutil
import subprocess

import configuration
from config_documents import Document, commit

MODULE_EXEC = 'set -e; . "$1"; module load "$2"; shift 2; exec "$@"'


def key():
    return (configuration.read() or {}).get('site', 'local')


def settings():
    document = Document(configuration.directory() / 'runtime.json')
    if not document.data:
        document.data = {'schema_version': 1, 'runtimes': {}}
    if document.data.get('schema_version') != 1 or not isinstance(document.data.get('runtimes'), dict):
        raise ValueError('Unsupported saved runtime configuration')
    return document


def executable(path):
    return Path(path).is_file() and os.access(path, os.X_OK)


def invocation(record):
    path = record.get('path', '')
    if not path or not Path(path).is_absolute() or not executable(path):
        raise ValueError('Saved Apptainer is unavailable on this node. Run ws runtime setup on the host to update it.')
    if record.get('module'):
        init = record.get('module_init', '')
        if not Path(init).is_absolute() or not Path(init).is_file():
            raise ValueError('Saved module initialization is unavailable; run ws runtime setup again')
        return ['/bin/bash', '--noprofile', '--norc', '-c', MODULE_EXEC, 'ws-runtime', init, record['module'], path]
    return [path]


def command():
    explicit = os.environ.get('WS_APPTAINER')
    if explicit:
        path = shutil.which(explicit)
        if not path:
            raise ValueError('WS_APPTAINER does not select an executable')
        return [str(Path(path).absolute())]
    available = shutil.which('apptainer')
    record = selected_record()
    if available and (not record or str(Path(available).absolute()) != record.get('path')):
        return [available]
    return invocation(record) if record else ['apptainer']


def selected_record():
    entries = settings().data['runtimes']
    return entries.get(key()) or (entries.get('local') if len(entries) == 1 else None)


def module_hint():
    matches = [item for item in os.environ.get('LOADEDMODULES', '').split(':')
               if item and any(name in item.lower() for name in ('apptainer', 'singularity'))]
    return matches[0] if len(matches) == 1 else None


def init_hint():
    candidates = []
    if os.environ.get('MODULESHOME'):
        candidates.append(Path(os.environ['MODULESHOME']) / 'init/bash')
    if os.environ.get('LMOD_CMD'):
        candidates.append(Path(os.environ['LMOD_CMD']).parent.parent / 'init/bash')
    candidates.extend(Path(p) for p in ('/etc/profile.d/lmod.sh', '/etc/profile.d/modules.sh'))
    return next((str(path.absolute()) for path in candidates if path.is_file()), None)


def probe(record, image):
    # A fresh process, without the currently loaded module's environment, establishes
    # whether the absolute path alone is sufficient. No full environment is saved.
    environment = {k: v for k, v in os.environ.items()
                   if k in ('HOME', 'USER', 'LOGNAME', 'TMPDIR', 'APPTAINER_TMPDIR',
                            'APPTAINER_CACHEDIR', 'APPTAINER_UNSQUASH')}
    environment.update(PATH='/usr/local/bin:/usr/bin:/bin', LANG='C')
    args = invocation(record) + ['exec', '--cleanenv', '--no-eval', '--no-mount', 'home,cwd,hostfs',
                                '--pwd', '/tmp', str(image), '/workspace-tools/bin/bash', '--noprofile', '--norc', '-c', 'exit 0']
    try:
        result = subprocess.run(args, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=120)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def setup(image, path=None, module=None, module_init=None, automatic=False):
    document = settings()
    prior = document.data['runtimes'].get(key(), {})
    found = path or os.environ.get('WS_APPTAINER') or shutil.which('apptainer') or prior.get('path')
    if not found:
        if automatic:
            return {'status': 'not available; load the module once, then run ws runtime setup'}
        raise ValueError('Load the site Apptainer module once, or pass --apptainer /absolute/path')
    found = shutil.which(found) or found
    record = {'path': str(Path(found).expanduser().absolute())}
    module = module or module_hint() or prior.get('module')
    module_init = module_init or init_hint() or prior.get('module_init')
    if not probe(record, image):
        if not module or not module_init:
            raise ValueError('Apptainer needs additional setup. Use ws runtime setup --module NAME --module-init FILE with the site module initialization file.')
        record.update(module=module, module_init=str(Path(module_init).expanduser().absolute()))
        if not probe(record, image):
            raise ValueError('Apptainer could not execute the workspace image with that module setup; saved configuration was preserved')
    record.update(validated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  validated_image=str(Path(image).resolve()))
    document.data['runtimes'][key()] = record
    commit([document], configuration.directory())
    return dict(record, status='ready', system=key())
