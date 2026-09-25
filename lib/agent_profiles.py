"""Named, private gateway profiles for the packaged agents. No network operations."""
import copy
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import configuration
from config_documents import Document, commit, toml_module

TOOLS = ('codex', 'claude')
CLAUDE_ROUTE_ENV = (
    'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN',
    'ANTHROPIC_BASE_URL', 'ANTHROPIC_CUSTOM_HEADERS', 'ANTHROPIC_MODEL',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL',
    'ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL',
    'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY',
    'ANTHROPIC_PROFILE',
)


def name_check(value):
    if value == 'none':
        raise ValueError('The profile name none is reserved; choose another gateway name')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,47}', value):
        raise ValueError('Use 1–48 lowercase letters, digits, underscores or hyphens')


def endpoint_check(value):
    try:
        parsed = urlsplit(value)
        parsed.port  # Validate a supplied port without normalizing the URL.
    except ValueError:
        raise ValueError('Enter a valid API base URL')
    if (parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or any(ord(c) < 33 for c in value)):
        raise ValueError('Use an http(s) base URL without credentials, query parameters or fragments')
    if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Use HTTPS for a gateway; HTTP is supported only for local testing')


def text_check(value):
    if not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError('Enter a nonempty value without control characters')


def env_check(value):
    if not re.fullmatch(r'[A-Z_][A-Z0-9_]*', value):
        raise ValueError('Use an environment variable name such as TEAM_API_KEY')
    if value in CLAUDE_ROUTE_ENV or value in ('OPENAI_API_KEY', 'CODEX_API_KEY'):
        raise ValueError('Use a distinct credential variable for this gateway, such as TEAM_API_KEY')


def catalog():
    document = Document(configuration.directory() / 'agents.json')
    if not document.data:
        document.data = {'schema_version': 1, 'profiles': {'codex': {}, 'claude': {}}, 'defaults': {}}
    data = document.data
    if data.get('schema_version') != 1 or not isinstance(data.get('profiles'), dict) or not isinstance(data.get('defaults'), dict):
        raise ValueError('Unsupported workspace agent catalog')
    for tool in TOOLS:
        if not isinstance(data['profiles'].get(tool, {}), dict):
            raise ValueError('Invalid agent profile list')
        data['profiles'].setdefault(tool, {})
    return document


def native_path(tool, name):
    name_check(name)
    if tool == 'codex':
        home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser()
        return home / ('ws-' + name + '.config.toml')
    home = Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude'))).expanduser()
    return home / 'workspace-profiles' / (name + '.json')


def documents(tool, name, index):
    if tool not in TOOLS:
        raise ValueError('Choose codex or claude')
    name_check(name)
    record = index.data['profiles'][tool].get(name)
    path = Path(record['path']) if record else native_path(tool, name)
    credential = (Path(record['credential']) if record else
                  configuration.directory() / 'credentials' / (tool + '-' + name + '.json'))
    native = Document(path, 'toml' if tool == 'codex' else 'json')
    secret = Document(credential, private=True)
    return native, secret


def values(tool, name, native, secret):
    if tool == 'codex':
        provider = native.data.get('model_providers', {}).get('ws-' + name, {})
        result = {'base_url': provider.get('base_url', ''), 'model': native.data.get('model', '')}
    else:
        result = {'base_url': native.data.get('env', {}).get('ANTHROPIC_BASE_URL', ''),
                  'model': native.data.get('model', '')}
    result.update(source=secret.data.get('source', 'stored'), variable=secret.data.get('variable', ''),
                  auth=secret.data.get('auth', 'bearer'))
    return result


def candidate(tool, name, native, secret, changes, key=None):
    """Edit only the managed connection fields, preserving unrelated native settings."""
    endpoint_check(changes['base_url'])
    text_check(changes['model'])
    if changes['source'] not in ('stored', 'environment'):
        raise ValueError('Unknown credential source')
    if changes['auth'] not in ('bearer', 'api-key') or (tool == 'codex' and changes['auth'] != 'bearer'):
        raise ValueError('Unsupported authentication mode for this agent')
    if changes['source'] == 'environment':
        env_check(changes['variable'])
    else:
        key = key if key is not None else secret.data.get('key')
        if not isinstance(key, str) or not key or any(ord(c) < 33 for c in key):
            raise ValueError('A nonempty key without whitespace is required')
    secret.data = {'schema_version': 1, 'tool': tool, 'name': name, 'source': changes['source'],
                   'base_url': changes['base_url'], 'auth': changes['auth']}
    if changes['source'] == 'environment':
        secret.data['variable'] = changes['variable']
    else:
        secret.data['key'] = key
    if tool == 'codex':
        provider_id = 'ws-' + name
        table = toml_module().table
        native.data['model'] = changes['model']
        native.data['model_provider'] = provider_id
        providers = native.data.setdefault('model_providers', table())
        provider = providers.setdefault(provider_id, table())
        provider.update(name=name, base_url=changes['base_url'], wire_api='responses',
                        env_key='WS_SELECTED_CODEX_KEY', requires_openai_auth=False)
        for field in ('auth', 'experimental_bearer_token', 'http_headers', 'env_http_headers', 'query_params'):
            if field in provider:
                del provider[field]
    else:
        native.data['model'] = changes['model']
        env = native.data.setdefault('env', {})
        if not isinstance(env, dict):
            raise ValueError('Claude env must be an object')
        for field in CLAUDE_ROUTE_ENV:
            env[field] = ''
        env['ANTHROPIC_BASE_URL'] = changes['base_url']
        # The credential is filled into a private, transient overlay at launch.
        # No secret enters argv or the reusable native preferences file.
        native.data['apiKeyHelper'] = ''
    return native, secret


def edit(form, tool, name=None):
    index = catalog()
    profiles = index.data['profiles'][tool]
    if name is None:
        selected = form.choose('Gateway profile', ['Add a gateway'] + sorted(profiles))
        name = form.text('Profile name (for example team-a)', check=name_check) if selected == 'Add a gateway' else selected
    name_check(name)
    native, secret = documents(tool, name, index)
    current = values(tool, name, native, secret)
    form.note('Native configuration: ' + str(native.path))
    form.note('Credential source: ' + str(secret.path) + ' (private)')
    operation = form.choose('Action', ['Edit connection', 'Rotate key', 'Use by default', 'Use ordinary agent settings']) if name in profiles else 'Edit connection'
    if operation in ('Use by default', 'Use ordinary agent settings'):
        if operation == 'Use by default':
            load_profile(tool, name)  # Check availability before selecting it.
            index.data['defaults'][tool] = name
        else:
            index.data['defaults'].pop(tool, None)
        form.note(tool + ' default: ' + (name if operation == 'Use by default' else 'ordinary settings'))
        if form.confirm('Save this default for new agent sessions?'):
            commit([index], configuration.directory())
        return
    proposed = dict(current)
    if operation == 'Edit connection':
        form.note('Use an OpenAI Responses endpoint.' if tool == 'codex' else 'Use an Anthropic Messages endpoint.')
        proposed['base_url'] = form.text('API base URL', current['base_url'], endpoint_check)
        proposed['model'] = form.text('Model identifier supplied by this gateway', current['model'], text_check)
        if tool == 'claude':
            proposed['auth'] = form.choose('Credential header', ['bearer', 'api-key'], current['auth'])
        proposed['source'] = form.choose('Credential source', ['stored', 'environment'], current['source'])
    key = None
    if proposed['source'] == 'environment':
        proposed['variable'] = form.text('Gateway-specific environment variable', current['variable'], env_check)
    else:
        retain = operation != 'Rotate key' and secret.data.get('key')
        choice = form.choose('Stored key', ['Keep existing key', 'Replace key']) if retain else 'Replace key'
        if choice == 'Replace key':
            key = form.text('API key (hidden)', secret=True, check=text_check)
    candidate(tool, name, native, secret, proposed, key)
    profiles[name] = {'path': str(native.link), 'credential': str(secret.link)}
    form.note('Changes for ' + tool + '/' + name + ':')
    for field in ('base_url', 'model', 'source', 'variable', 'auth'):
        if current.get(field) != proposed.get(field):
            form.note('  {}: {} -> {}'.format(field, current.get(field) or '(unset)', proposed.get(field) or '(unset)'))
    form.note('  API key: ' + ('replaced (hidden)' if key is not None else 'retained / provided by environment'))
    form.note('Unrelated settings are retained. Managed connection/auth fields use the chosen gateway.')
    if form.confirm('Save this profile and its private credential source?'):
        commit([native, secret, index], configuration.directory())
        form.note('Saved. Start with: ws agent ' + tool + ' ' + name)
        form.note('Reopen this form to select it as the default or rotate its key.')


def load_profile(tool, name):
    index = catalog()
    if name not in index.data['profiles'][tool]:
        raise ValueError('Unknown gateway profile; use ws configure ' + tool)
    native, credential = documents(tool, name, index)
    data = credential.data
    current = values(tool, name, native, credential)
    if (data.get('schema_version') != 1 or data.get('tool') != tool or data.get('name') != name
            or data.get('base_url') != current['base_url']):
        raise ValueError('Gateway endpoint or credential binding changed; review it with ws configure ' + tool + ' ' + name)
    if data.get('auth') not in ('bearer', 'api-key') or (tool == 'codex' and data['auth'] != 'bearer'):
        raise ValueError('Unsupported gateway authentication mode')
    if tool == 'codex':
        provider = native.data.get('model_providers', {}).get('ws-' + name, {})
        if (native.data.get('model_provider') != 'ws-' + name or provider.get('env_key') != 'WS_SELECTED_CODEX_KEY'
                or provider.get('wire_api') != 'responses' or provider.get('requires_openai_auth') is not False
                or any(field in provider for field in ('auth', 'experimental_bearer_token', 'http_headers', 'env_http_headers', 'query_params'))):
            raise ValueError('Managed Codex authentication fields changed; review the gateway with ws configure codex ' + name)
    endpoint_check(current['base_url'])
    text_check(current['model'])
    if data.get('source') == 'environment':
        env_check(data.get('variable', ''))
        key = os.environ.get(data['variable'])
    elif data.get('source') == 'stored':
        key = data.get('key')
    else:
        raise ValueError('Unsupported credential source')
    if not isinstance(key, str) or not key or any(ord(c) < 33 for c in key):
        raise ValueError('Selected gateway credential is unavailable; update it with ws configure ' + tool + ' ' + name)
    return native, data, key


def launch_profile(tool, arguments, environment):
    """Return selected native arguments/env and an optional temporary JSON overlay."""
    requested = environment.pop('WS_AGENT_PROFILE', None)
    if requested == 'none':
        return list(arguments), environment, None
    name = requested or catalog().data['defaults'].get(tool)
    if not name:
        return list(arguments), environment, None
    name_check(name)
    if tool == 'codex':
        forbidden = ('--profile', '-p', '--remote', '--oss', '--local-provider')
        if any(arg.split('=', 1)[0] in forbidden or (arg.startswith('-p') and not arg.startswith('--')) for arg in arguments):
            raise ValueError('A gateway profile is active. Use ws agent codex --native for native profile/remote options.')
        overrides = []
        for index, arg in enumerate(arguments):
            if arg in ('-c', '--config') and index + 1 < len(arguments):
                overrides.append(arguments[index + 1])
            elif arg.startswith('--config='):
                overrides.append(arg.split('=', 1)[1])
            elif arg.startswith('-c') and len(arg) > 2:
                overrides.append(arg[2:])
        if any(value.split('=', 1)[0].strip().startswith(('model_providers', 'model_provider', 'openai_base_url')) for value in overrides):
            raise ValueError('Edit the selected gateway through ws configure before overriding its route')
    elif any(arg.split('=', 1)[0] in ('--settings', '--setting-sources') for arg in arguments):
        raise ValueError('A gateway profile is active. Use ws agent claude --native for other settings overlays.')
    native, credential, key = load_profile(tool, name)
    if tool == 'codex':
        home = Path(environment.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()
        if native.path != (home / ('ws-' + name + '.config.toml')).resolve():
            raise ValueError('CODEX_HOME changed; configure this gateway in the selected Codex home first')
        for field in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'WS_SELECTED_CODEX_KEY'):
            environment.pop(field, None)
        environment['WS_SELECTED_CODEX_KEY'] = key
        return ['--profile', 'ws-' + name] + list(arguments), environment, None
    overlay = copy.deepcopy(native.data)
    env = overlay.setdefault('env', {})
    for field in CLAUDE_ROUTE_ENV:
        environment.pop(field, None)
        env[field] = ''
    env['ANTHROPIC_BASE_URL'] = credential['base_url']
    env['ANTHROPIC_AUTH_TOKEN' if credential['auth'] == 'bearer' else 'ANTHROPIC_API_KEY'] = key
    overlay['apiKeyHelper'] = ''
    environment['ANTHROPIC_BASE_URL'] = credential['base_url']
    return list(arguments), environment, overlay
