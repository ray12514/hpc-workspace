"""Real terminal forms and packaged-agent routing against loopback-only HTTP fixtures."""
import argparse
import http.server
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import signal
import ssl
import subprocess
import struct
import sys
import tempfile
import termios
import threading
import time

sys.path.insert(0, '/workspace-tools/lib')
import agent_profiles as profiles
from config_documents import commit

ROOT = Path('/workspace-tools')
PYTHON = str(ROOT / 'libexec/python3')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--forms-only', action='store_true', help='Run terminal checks without launching agents')
args = parser.parse_args()


def check_form_contrast(environment):
    """Real Gum must leave text in the terminal's readable foreground/background."""
    program = """import os, sys
sys.path.insert(0, '/workspace-tools/lib')
from terminal_forms import Form
before = dict(os.environ)
form = Form()
assert form.text('API base URL', 'https://fixture.example.invalid/v1') == 'https://fixture.example.invalid/v1'
assert form.text('Model identifier') == 'fixture-model'
assert form.choose('Credential source', ['Stored key', 'Environment variable']) == 'Environment variable'
assert dict(os.environ) == before, 'Form changed the parent color environment'
print('CONTRAST_OK')
"""
    code, output = terminal([PYTHON, '-I', '-c', program],
                            [('https://fixture.example.invalid/v1', b'\r'),
                             ('Model identifier', b'fixture-model'), ('fixture-model', b'\r'),
                             ('Stored key', b'\x1b[B\r'), ('CONTRAST_OK', b'')], environment)
    assert code == 0, 'Contrast fixture did not complete'
    for text in (b'API base URL', b'Model identifier', b'Credential source', b'Environment variable'):
        assert text in output, 'Form omitted a label or option'
    # A fixed color can be unreadable on a user's light/dark palette. Retaining
    # default colors also keeps the help and placeholder legible; cursor reverse
    # video and ordinary emphasis remain permitted.
    fixed_colors = set(range(30, 38)) | set(range(40, 48)) | set(range(90, 98)) | set(range(100, 108)) | {38, 48}
    for match in re.finditer(rb'\x1b\[([0-9:;]*)m', output):
        parameters = {int(value) for value in re.split(rb'[;:]', match[1]) if value}
        assert not parameters & (fixed_colors | {2, 8}), 'Form overrides readable terminal colors: ' + repr(match[0])


def create(tool, name, endpoint, key, auth='bearer', api='openai-responses', ca_bundle=None):
    index = profiles.catalog()
    native, secret = profiles.documents(tool, name, index)
    profiles.candidate(tool, name, native, secret,
                       dict(base_url=endpoint, model='fixture-model', source='stored', variable='',
                            auth=auth, api=api, ca_bundle=ca_bundle), key)
    index.data['profiles'][tool][name] = {'path': str(native.path), 'credential': str(secret.path)}
    commit([native, secret, index], os.environ['WS_CONFIG_DIR'])
    return native.path, secret.path


def terminal(command, steps, env):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
    process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True)
    os.close(slave)
    transcript = b''
    try:
        for expected, answer in steps:
            deadline = time.monotonic() + 20
            chunk = b''
            while expected.encode() not in chunk:
                if time.monotonic() > deadline or process.poll() is not None:
                    raise AssertionError('Terminal did not reach expected prompt: ' + expected)
                if select.select([master], [], [], .1)[0]:
                    data = os.read(master, 65536)
                    chunk += data
                    transcript += data
            os.write(master, answer)
        deadline = time.monotonic() + 20
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]:
                try:
                    transcript += os.read(master, 65536)
                except OSError:
                    break
        result = process.wait(timeout=3)
        return result, transcript
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        os.close(master)


with tempfile.TemporaryDirectory(prefix='ws-configuration-acceptance-') as temporary:
    home = Path(temporary)
    os.environ.update(HOME=str(home), CODEX_HOME=str(home / 'codex'), PI_CODING_AGENT_DIR=str(home / 'pi'),
                      WS_CONFIG_DIR=str(home / 'workspace'), TERM='xterm-256color')
    for variable in list(os.environ):
        if variable.startswith('ANTHROPIC_') or variable in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'WS_AGENT_PROFILE'):
            del os.environ[variable]
    # PuTTY-compatible TERM values, tmux, and inherited themes must all preserve
    # the terminal's normal contrast. No terminal background query is answered.
    for term, overrides in (
            ('xterm', {}),
            ('xterm-256color', {'COLORTERM': 'truecolor'}),
            ('screen-256color', {}),
            ('tmux-256color', {'GUM_INPUT_HEADER_FOREGROUND': '0', 'GUM_INPUT_HEADER_BACKGROUND': '0',
                               'GUM_INPUT_PROMPT_FOREGROUND': '0', 'GUM_INPUT_PLACEHOLDER_FOREGROUND': '0',
                               'GUM_CHOOSE_ITEM_FOREGROUND': '0', 'GUM_CHOOSE_SELECTED_FOREGROUND': '0',
                               'CLICOLOR_FORCE': '1', 'FORCE_COLOR': '3'})):
        environment = dict(os.environ, TERM=term)
        for key in ('NO_COLOR', 'CLICOLOR', 'CLICOLOR_FORCE', 'FORCE_COLOR', 'COLORTERM'):
            environment.pop(key, None)
        environment.update(overrides)
        check_form_contrast(environment)
    # Real Gum selection/input and cancellation, including a masked synthetic key.
    hidden = 'synthetic-hidden-' + 'x' * 600
    snippet = "from terminal_forms import Form; f=Form(); assert f.choose('Fixture menu',['One','Two'])=='Two'; assert f.text('Fixture secret',secret=True)==" + repr(hidden) + "; print('FORM_OK')"
    program = "import sys; sys.path.insert(0,'/workspace-tools/lib'); " + snippet
    code, output = terminal([PYTHON, '-I', '-c', program],
                            [('One', b'\x1b[B\r'), ('Fixture secret', hidden.encode() + b'\r'), ('FORM_OK', b'')], dict(os.environ))
    assert code == 0
    assert b'synthetic-hidden' not in output, 'Gum echoed a hidden input'
    before = list(home.rglob('*.json'))
    code, output = terminal([PYTHON, '-I', '/workspace-tools/bin/ws', 'configure', 'pi', 'cancelled'],
                            [('API base URL', b'\x03')], dict(os.environ))
    assert code == 130
    assert list(home.rglob('*.json')) == before, 'Cancel wrote configuration'
    # Full plain-prompt edits keep each CA choice with the hidden gateway key.
    form_ca = home / 'form-ca.pem'
    form_ca.write_text('-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n')
    code, output = terminal([PYTHON, '-I', '/workspace-tools/bin/ws', 'configure', 'pi', 'plain', '--plain'],
                            [('API base URL:', b'https://plain.example.invalid\n'),
                             ('Model identifier', b'fixture-model\n'),
                             ('Agent CA bundle path', str(form_ca).encode() + b'\n'),
                             ('Gateway API protocol', b'1\n'),
                             ('Credential header', b'1\n'),
                             ('Credential source', b'1\n'), ('API key (hidden)', b'plain-hidden-key\n'),
                             ('Save this profile', b'2\n')], dict(os.environ))
    assert code == 0
    assert b'plain-hidden-key' not in output
    assert profiles.load_profile('pi', 'plain')[2] == 'plain-hidden-key'
    assert profiles.load_profile('pi', 'plain')[1]['ca_bundle'] == str(form_ca)
    code, output = terminal([PYTHON, '-I', '/workspace-tools/bin/ws', 'configure', 'codex', 'plain-codex', '--plain'],
                            [('API base URL:', b'https://plain-codex.example.invalid/v1\n'),
                             ('Model identifier', b'fixture-model\n'),
                             ('Agent CA bundle path', str(form_ca).encode() + b'\n'),
                             ('Credential source', b'1\n'), ('API key (hidden)', b'plain-codex-hidden-key\n'),
                             ('Save this profile', b'2\n')], dict(os.environ))
    assert code == 0
    assert b'plain-codex-hidden-key' not in output
    assert profiles.load_profile('codex', 'plain-codex')[1]['ca_bundle'] == str(form_ca)
    if args.forms_only:
        print('PASS: terminal contrast, selection, typed/saved values, masked input, cancellation, and plain forms')
        raise SystemExit(0)
    captured = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            captured.append((self.path, self.headers.get('Authorization'), self.headers.get('x-api-key')))
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"type":"error","error":{"type":"authentication_error","message":"local fixture"}}')
        def do_GET(self):
            self.send_response(404)
            self.end_headers()
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:' + str(server.server_address[1])
    try:
        for tool, name, auth, api in [('codex', 'one', 'bearer', 'openai-responses'),
                                      ('codex', 'two', 'bearer', 'openai-responses'),
                                      ('pi', 'one', 'bearer', 'openai-responses'),
                                      ('pi', 'two', 'api-key', 'openai-responses'),
                                      ('pi', 'three', 'api-key', 'anthropic-messages')]:
            expected = 'synthetic-key-' + tool + '-' + name
            create(tool, name, base + '/v1', expected, auth, api)
            environment = dict(os.environ, WS_AGENT_PROFILE=name, OPENAI_API_KEY='wrong-key',
                               ANTHROPIC_API_KEY='wrong-key', ANTHROPIC_AUTH_TOKEN='wrong-token')
            # Existing user settings try to reintroduce the wrong route and auth.
            if tool == 'pi':
                user = Path(environment['PI_CODING_AGENT_DIR']) / 'settings.json'
                user.write_text(json.dumps({'defaultProvider': 'openai', 'defaultModel': 'wrong-model'}))
            command = [str(ROOT / 'bin' / tool)]
            command += (['--strict-config', 'exec', '--skip-git-repo-check', 'fixture request'] if tool == 'codex'
                        else ['--print', '--no-session', '--no-tools', '--', 'fixture request'])
            captured.clear()
            child = subprocess.Popen(command, cwd=str(home), env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                stdout, stderr = child.communicate(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                stdout, stderr = child.communicate()
            assert captured, 'No local request from ' + tool + ': ' + stderr.decode(errors='replace')[-1200:]
            for path, bearer, api_key in captured:
                selected = bearer if auth == 'bearer' else api_key
                assert selected == ('Bearer ' + expected if auth == 'bearer' else expected), 'Wrong selected credential for ' + tool
                if auth == 'api-key':
                    assert not bearer or expected not in bearer, 'Selected key leaked to a second header'
                assert 'wrong' not in str((bearer, api_key)), 'Inherited credential reached the gateway'
            assert expected.encode() not in stdout + stderr, 'Credential appeared in agent output'
        # Rotation is observed by the next launch and does not alter the other profile.
        native, secret = profiles.documents('pi', 'one', profiles.catalog())
        old = native.path.read_bytes()
        profiles.candidate('pi', 'one', native, secret, profiles.values('pi', 'one', native, secret), 'synthetic-rotated')
        commit([native, secret], os.environ['WS_CONFIG_DIR'])
        assert native.path.read_bytes() == old
        assert profiles.load_profile('pi', 'one')[2] == 'synthetic-rotated'
        assert profiles.load_profile('pi', 'two')[2] == 'synthetic-key-pi-two'
        # Pi's bundled runtime must trust a site CA supplied through the
        # workspace's usual SSL_CERT_FILE, without disabling TLS verification.
        certificate = home / 'fixture-ca.pem'
        ca_key = home / 'fixture-ca.key'
        server_certificate = home / 'fixture-server.pem'
        private_key = home / 'fixture-server.key'
        request = home / 'fixture-server.csr'
        extensions = home / 'fixture-server.ext'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(ca_key), '-out', str(certificate), '-days', '1',
                        '-subj', '/CN=fixture-ca', '-addext', 'basicConstraints=critical,CA:TRUE',
                        '-addext', 'keyUsage=critical,keyCertSign,cRLSign'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(private_key), '-out', str(request), '-subj', '/CN=localhost'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        extensions.write_text('basicConstraints=critical,CA:FALSE\n'
                              'keyUsage=critical,digitalSignature,keyEncipherment\n'
                              'extendedKeyUsage=serverAuth\nsubjectAltName=IP:127.0.0.1\n')
        subprocess.run(['openssl', 'x509', '-req', '-in', str(request), '-CA', str(certificate),
                        '-CAkey', str(ca_key), '-CAcreateserial', '-out', str(server_certificate),
                        '-days', '1', '-extfile', str(extensions)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        secure_server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(server_certificate), str(private_key))
        secure_server.socket = context.wrap_socket(secure_server.socket, server_side=True)
        threading.Thread(target=secure_server.serve_forever, daemon=True).start()
        try:
            create('codex', 'secure-codex',
                   'https://127.0.0.1:' + str(secure_server.server_address[1]) + '/v1',
                   'synthetic-secure-codex-key', ca_bundle=str(certificate))
            environment = dict(os.environ, WS_AGENT_PROFILE='secure-codex')
            for variable in ('CODEX_CA_CERTIFICATE', 'SSL_CERT_FILE', 'CURL_CA_BUNDLE',
                             'REQUESTS_CA_BUNDLE', 'NODE_EXTRA_CA_CERTS'):
                environment.pop(variable, None)
            captured.clear()
            child = subprocess.Popen([str(ROOT / 'bin/codex'), '--strict-config', 'exec',
                                      '--skip-git-repo-check', 'fixture request'], cwd=str(home),
                                     env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True)
            deadline = time.monotonic() + 15
            while not captured and child.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            _, stderr = child.communicate(timeout=3)
            assert captured, 'Codex did not trust the selected gateway CA: ' + stderr.decode(errors='replace')[-1200:]
            assert any(bearer == 'Bearer synthetic-secure-codex-key' for _, bearer, _ in captured)
            create('pi', 'secure', 'https://127.0.0.1:' + str(secure_server.server_address[1]) + '/v1',
                   'synthetic-secure-key')
            environment = dict(os.environ, WS_AGENT_PROFILE='secure', SSL_CERT_FILE=str(certificate))
            environment.pop('NODE_EXTRA_CA_CERTS', None)
            captured.clear()
            child = subprocess.run([str(ROOT / 'bin/pi'), '--print', '--no-session', '--no-tools', '--',
                                    'fixture request'], cwd=str(home), env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
            assert captured, 'Pi did not trust the selected site CA: ' + child.stderr.decode(errors='replace')[-1200:]
            assert any(bearer == 'Bearer synthetic-secure-key' for _, bearer, _ in captured)
            create('pi', 'secure-profile',
                   'https://127.0.0.1:' + str(secure_server.server_address[1]) + '/v1',
                   'synthetic-secure-profile-key', ca_bundle=str(certificate))
            environment = dict(os.environ, WS_AGENT_PROFILE='secure-profile')
            for variable in ('SSL_CERT_FILE', 'NODE_EXTRA_CA_CERTS'):
                environment.pop(variable, None)
            captured.clear()
            child = subprocess.run([str(ROOT / 'bin/pi'), '--print', '--no-session', '--no-tools', '--',
                                    'fixture request'], cwd=str(home), env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
            assert captured, 'Pi did not trust its selected gateway CA: ' + child.stderr.decode(errors='replace')[-1200:]
            assert any(bearer == 'Bearer synthetic-secure-profile-key' for _, bearer, _ in captured)
        finally:
            secure_server.shutdown()
    finally:
        server.shutdown()
    print('PASS: terminal contrast, Gum and plain forms, cancellation, masked input, Codex/Pi gateway routing, selected Codex/Pi CA trust, stale-auth cleanup, and key rotation')
