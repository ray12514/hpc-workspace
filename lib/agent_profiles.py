"""Named, private gateway profiles for the packaged agents. No network operations."""
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import configuration
from config_documents import Document, commit, toml_module

TOOLS = ('codex', 'pi')
PI_APIS = ('openai-responses', 'openai-completions', 'anthropic-messages')
PI_KEY_VARIABLE = 'WS_SELECTED_PI_KEY'


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
    if value in (PI_KEY_VARIABLE, 'OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY'):
        raise ValueError('Use a distinct credential variable for this gateway, such as TEAM_API_KEY')


def catalog():
    document = Document(configuration.directory() / 'agents.json')
    if not document.data:
        document.data = {'schema_version': 1, 'profiles': {'codex': {}, 'pi': {}}, 'defaults': {}}
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
    home = Path(os.environ.get('PI_CODING_AGENT_DIR', str(Path.home() / '.pi/agent'))).expanduser()
    return home / 'models.json'


def documents(tool, name, index):
    if tool not in TOOLS:
        raise ValueError('Choose codex or pi')
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
        provider = native.data.get('providers', {}).get('ws-' + name, {})
        models = provider.get('models', [])
        result = {'base_url': provider.get('baseUrl', ''),
                  'model': models[0].get('id', '') if models else '',
                  'api': provider.get('api', 'openai-responses')}
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
    if tool == 'pi' and changes['api'] not in PI_APIS:
        raise ValueError('Choose a supported Pi API protocol')
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
    if tool == 'pi':
        secret.data['api'] = changes['api']
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
        providers = native.data.setdefault('providers', {})
        if not isinstance(providers, dict):
            raise ValueError('Pi providers must be an object')
        provider = {'name': name, 'baseUrl': changes['base_url'], 'api': changes['api'],
                    'apiKey': '$' + PI_KEY_VARIABLE if changes['auth'] == 'bearer' else 'workspace-profile',
                    'authHeader': changes['auth'] == 'bearer', 'models': [{'id': changes['model']}]}
        if changes['auth'] == 'api-key':
            provider['headers'] = {'x-api-key': '$' + PI_KEY_VARIABLE}
        providers['ws-' + name] = provider
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
        form.note('Use an OpenAI Responses endpoint.' if tool == 'codex' else 'Choose the API protocol exposed by the gateway.')
        proposed['base_url'] = form.text('API base URL', current['base_url'], endpoint_check)
        proposed['model'] = form.text('Model identifier supplied by this gateway', current['model'], text_check)
        if tool == 'pi':
            proposed['api'] = form.choose('Gateway API protocol', list(PI_APIS), current['api'])
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
    for field in ('base_url', 'model', 'api', 'source', 'variable', 'auth'):
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
    else:
        provider = native.data.get('providers', {}).get('ws-' + name, {})
        expected = {'name': name, 'baseUrl': current['base_url'], 'api': current['api'],
                    'apiKey': '$' + PI_KEY_VARIABLE if data['auth'] == 'bearer' else 'workspace-profile',
                    'authHeader': data['auth'] == 'bearer', 'models': [{'id': current['model']}]}
        if data['auth'] == 'api-key':
            expected['headers'] = {'x-api-key': '$' + PI_KEY_VARIABLE}
        if provider != expected or data.get('api') != current['api']:
            raise ValueError('Managed Pi provider changed; review it with ws configure pi ' + name)
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
    """Return selected native arguments/env; secrets remain in child environment."""
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
    elif any(arg.split('=', 1)[0] in ('--provider', '--model', '--api-key', '--models') for arg in arguments):
        raise ValueError('A gateway profile is active. Use ws agent pi --native for other model options.')
    native, credential, key = load_profile(tool, name)
    if tool == 'codex':
        home = Path(environment.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()
        if native.path != (home / ('ws-' + name + '.config.toml')).resolve():
            raise ValueError('CODEX_HOME changed; configure this gateway in the selected Codex home first')
        for field in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'WS_SELECTED_CODEX_KEY'):
            environment.pop(field, None)
        environment['WS_SELECTED_CODEX_KEY'] = key
        return ['--profile', 'ws-' + name] + list(arguments), environment, None
    home = Path(environment.get('PI_CODING_AGENT_DIR', str(Path.home() / '.pi/agent'))).expanduser().resolve()
    if native.path != (home / 'models.json').resolve():
        raise ValueError('PI_CODING_AGENT_DIR changed; configure this gateway in the selected Pi home first')
    auth_path = home / 'auth.json'
    if auth_path.exists() and ('ws-' + name) in json.loads(auth_path.read_text()):
        raise ValueError('Remove the stored Pi credential for ws-' + name + ' before using this workspace profile')
    for field in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', PI_KEY_VARIABLE):
        environment.pop(field, None)
    environment[PI_KEY_VARIABLE] = key
    return ['--provider', 'ws-' + name, '--model', current_model(native, name)] + list(arguments), environment, None


def current_model(native, name):
    return native.data['providers']['ws-' + name]['models'][0]['id']
