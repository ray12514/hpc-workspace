"""Track the workspace's own environment changes for remote job submission."""
import json


PRIVATE_ROOTS = ('/workspace-tools', '/workspace-state', '/workspace-bootstrap')
RUNTIME_KEYS = {
    'WS_CONTAINER', 'WS_ROOT', 'WS_RELEASE', 'WS_LAYOUT', 'WS_STATE_HOME',
    'WS_PROJECT', 'WS_GPU_MODE', 'WS_SITE', 'WS_HOSTNAME', 'WS_CONTEXT',
    'WS_SESSION_STATE', 'WS_HOST_JOBS_SOCKET', 'WS_ENV_RESTORE', 'TMUX', 'TMUX_PANE',
}


def apply_overrides(environment, updates):
    """Remember only values we replace, never an entire credential-bearing environment."""
    original = json.loads(environment.get('WS_ENV_RESTORE', '{}'))
    for key, value in updates.items():
        before = original[key][0] if key in original else environment.get(key)
        original[key] = [before, value]
        environment[key] = value
    environment['WS_ENV_RESTORE'] = json.dumps(original, separators=(',', ':'))


def job_environment(environment):
    """Remove image-only additions; retain current site/module/user changes."""
    result = dict(environment)
    for key, (before, applied) in json.loads(result.get('WS_ENV_RESTORE', '{}')).items():
        # A subsequent explicit user setting takes precedence over our default.
        if key not in ('PATH', 'TERMINFO_DIRS') and result.get(key) == applied:
            if before is None:
                result.pop(key, None)
            else:
                result[key] = before
    for key in ('PATH', 'TERMINFO_DIRS'):
        if key in result:
            result[key] = ':'.join(path for path in result[key].split(':')
                                   if not any(path == root or path.startswith(root + '/')
                                              for root in PRIVATE_ROOTS))
    for key in list(result):
        if key in RUNTIME_KEYS or key.startswith(('APPTAINER', 'SINGULARITY')):
            result.pop(key)
    return result
