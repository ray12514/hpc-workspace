"""Real terminal forms and packaged-agent routing against loopback-only HTTP fixtures."""
import http.server
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
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


def create(tool, name, endpoint, key, auth='bearer'):
    index = profiles.catalog()
    native, secret = profiles.documents(tool, name, index)
    profiles.candidate(tool, name, native, secret,
                       dict(base_url=endpoint, model='fixture-model', source='stored', variable='', auth=auth), key)
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
    os.environ.update(HOME=str(home), CODEX_HOME=str(home / 'codex'), CLAUDE_CONFIG_DIR=str(home / 'claude'),
                      WS_CONFIG_DIR=str(home / 'workspace'), TERM='xterm-256color')
    for variable in list(os.environ):
        if variable.startswith(('ANTHROPIC_', 'CLAUDE_CODE_USE_')) or variable in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'WS_AGENT_PROFILE'):
            del os.environ[variable]
    # Real Gum selection/input and cancellation, including a masked synthetic key.
    hidden = 'synthetic-hidden-' + 'x' * 600
    snippet = "from terminal_forms import Form; f=Form(); assert f.choose('Fixture menu',['One','Two'])=='Two'; assert f.text('Fixture secret',secret=True)==" + repr(hidden) + "; print('FORM_OK')"
    program = "import sys; sys.path.insert(0,'/workspace-tools/lib'); " + snippet
    code, output = terminal([PYTHON, '-I', '-c', program],
                            [('One', b'\x1b[B\r'), ('Fixture secret', hidden.encode() + b'\r'), ('FORM_OK', b'')], dict(os.environ))
    assert code == 0
    assert b'synthetic-hidden' not in output, 'Gum echoed a hidden input'
    before = list(home.rglob('*.json'))
    code, output = terminal([PYTHON, '-I', '/workspace-tools/bin/ws', 'configure', 'claude', 'cancelled'],
                            [('API base URL', b'\x03')], dict(os.environ))
    assert code == 130
    assert list(home.rglob('*.json')) == before, 'Cancel wrote configuration'
    # A full plain-prompt edit uses the same backend and key masking.
    code, output = terminal([PYTHON, '-I', '/workspace-tools/bin/ws', 'configure', 'claude', 'plain', '--plain'],
                            [('API base URL:', b'https://plain.example.invalid\n'),
                             ('Model identifier', b'fixture-model\n'), ('Credential header', b'1\n'),
                             ('Credential source', b'1\n'), ('API key (hidden)', b'plain-hidden-key\n'),
                             ('Save this profile', b'2\n')], dict(os.environ))
    assert code == 0
    assert b'plain-hidden-key' not in output
    assert profiles.load_profile('claude', 'plain')[2] == 'plain-hidden-key'
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
        for tool, name, auth in [('codex', 'one', 'bearer'), ('codex', 'two', 'bearer'),
                                 ('claude', 'one', 'bearer'), ('claude', 'two', 'api-key')]:
            expected = 'synthetic-key-' + tool + '-' + name
            create(tool, name, base + ('/v1' if tool == 'codex' else ''), expected, auth)
            environment = dict(os.environ, WS_AGENT_PROFILE=name, OPENAI_API_KEY='wrong-key',
                               ANTHROPIC_API_KEY='wrong-key', ANTHROPIC_AUTH_TOKEN='wrong-token',
                               CLAUDE_CODE_USE_BEDROCK='1', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1')
            # Existing user settings try to reintroduce the wrong route and auth.
            if tool == 'claude':
                user = Path(environment['CLAUDE_CONFIG_DIR']) / 'settings.json'
                user.write_text(json.dumps({'env': {'ANTHROPIC_AUTH_TOKEN': 'wrong-from-settings',
                                                    'ANTHROPIC_BASE_URL': 'http://127.0.0.1:1',
                                                    'CLAUDE_CODE_USE_VERTEX': '1'}}))
            command = [str(ROOT / 'bin' / tool)]
            command += (['--strict-config', 'exec', '--skip-git-repo-check', 'fixture request'] if tool == 'codex'
                        else ['--print', '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--', 'fixture request'])
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
                assert 'wrong' not in str((bearer, api_key)), 'Inherited credential reached the gateway'
            assert expected.encode() not in stdout + stderr, 'Credential appeared in agent output'
        # Rotation is observed by the next launch and does not alter the other profile.
        native, secret = profiles.documents('claude', 'one', profiles.catalog())
        old = native.path.read_bytes()
        profiles.candidate('claude', 'one', native, secret, profiles.values('claude', 'one', native, secret), 'synthetic-rotated')
        commit([native, secret], os.environ['WS_CONFIG_DIR'])
        assert native.path.read_bytes() == old
        assert profiles.load_profile('claude', 'one')[2] == 'synthetic-rotated'
        assert profiles.load_profile('claude', 'two')[2] == 'synthetic-key-claude-two'
    finally:
        server.shutdown()
    print('PASS: Gum and plain forms, cancellation, masked input, actual Codex/Claude gateway routing, stale-auth cleanup, and key rotation')
