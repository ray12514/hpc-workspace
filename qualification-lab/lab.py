#!/usr/bin/env python3
"""Loopback-only, single-operator HPC qualification workspace. Python 3.9+."""
import argparse
import copy
import hashlib
import html
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 8 * 1024 * 1024


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Workspace must be an object')
    for collection in ('experiments', 'platforms', 'adrs'):
        rows = data.get(collection)
        if not isinstance(rows, list):
            raise ValueError('Missing collection: ' + collection)
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids:
                raise ValueError('Invalid or duplicate ID in ' + collection)
            ids.add(row['id'])
    string_fields = ('title', 'app', 'input', 'quality', 'platform', 'stack', 'mode', 'domain', 'baseline', 'hypothesis', 'change', 'measurement', 'recoveryPlan', 'tradeoff')
    for e in data['experiments']:
        if not all(isinstance(e.get(k), str) for k in string_fields):
            raise ValueError('Invalid experiment fields')
        for k in ('tolerance', 'regression'):
            if not finite_nonnegative(e.get(k)):
                raise ValueError('Invalid experiment tolerance')
        if not isinstance(e.get('history'), list) or not isinstance(e.get('runs'), list):
            raise ValueError('Invalid experiment history')
        seen = set()
        for r in e['runs']:
            if not isinstance(r, dict) or not isinstance(r.get('id'), str) or r['id'] in seen:
                raise ValueError('Invalid or duplicate run ID')
            seen.add(r['id'])
            samples = r.get('samples')
            if not isinstance(samples, list) or not samples or not all(finite_nonnegative(n) and n > 0 for n in samples):
                raise ValueError('Invalid measured samples')
            if not finite_nonnegative(r.get('error')) or not finite_nonnegative(r.get('cost')):
                raise ValueError('Invalid run error or cost')
            if not all(isinstance(r.get(k), str) for k in ('date', 'kind', 'artifact', 'config', 'notes', 'contract', 'planSnapshot')):
                raise ValueError('Invalid run snapshot')
            for k in ('correctness', 'recovery', 'operations'):
                if r.get(k) not in ('Pass', 'Fail', 'Not tested'):
                    raise ValueError('Invalid gate result')
            json.loads(r['contract'])
    for p in data['platforms']:
        if not all(isinstance(p.get(k), str) for k in ('name', 'hardware', 'fabric', 'scheduler', 'stack', 'tier', 'lifecycle', 'notes')) or not isinstance(p.get('history'), list):
            raise ValueError('Invalid platform')
    for a in data['adrs']:
        if not all(isinstance(a.get(k), str) for k in ('title', 'context', 'decision', 'alternatives', 'consequences', 'evidence', 'date')):
            raise ValueError('Invalid decision record')
    return data


def finite_nonnegative(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path, system_id):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', system_id):
            raise ValueError('System ID must be 1–64 letters, digits, underscores or hyphens')
        self.path = Path(path).expanduser().resolve()
        self.system_id = system_id
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL, revision INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            old = db.execute("SELECT value FROM metadata WHERE key='system_id'").fetchone()
            if old and old[0] != system_id:
                raise ValueError('This database belongs to system ' + old[0] + '; use that --system-id or a separate --data path')
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('system_id', ?)", (system_id,))
            db.execute('INSERT OR IGNORE INTO workspace VALUES (1, ?, 1)', (canonical(self.initial()),))
        os.chmod(self.path, 0o600)

    def connect(self):
        return sqlite3.connect(str(self.path), timeout=10)

    def initial(self):
        data = json.loads((ROOT / 'seed.json').read_text())
        prefix = self.system_id + '::'
        for e in data['experiments']:
            e['id'] = prefix + e['id']
            e['platform'] = prefix + e['platform']
        for p in data['platforms']:
            p['id'] = prefix + p['id']
        return data

    def get(self):
        with self.connect() as db:
            raw, rev = db.execute('SELECT data, revision FROM workspace WHERE id=1').fetchone()
        return {'data': json.loads(raw), 'revision': rev}

    def put(self, data, revision):
        validate(data)
        if not isinstance(revision, int) or isinstance(revision, bool):
            raise ValueError('Invalid revision')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            raw, current = db.execute('SELECT data, revision FROM workspace WHERE id=1').fetchone()
            if revision != current:
                raise Conflict('Workspace changed. Export unsaved edits and reload before retrying.')
            # UI edits may append runs; historical measurement snapshots cannot be altered or removed.
            old = json.loads(raw)
            imports = [row[0].split(':', 1)[1] + '::' for row in db.execute("SELECT key FROM metadata WHERE key LIKE 'ingest:%'")]
            for collection in ('experiments', 'platforms', 'adrs'):
                incoming_records = {row['id']: row for row in data[collection]}
                for row in old[collection]:
                    if any(row['id'].startswith(prefix) for prefix in imports) and incoming_records.get(row['id']) != row:
                        raise ValueError('Imported source records are read-only in the master. Edit at the source and re-import.')
            incoming = {e['id']: e for e in data['experiments']}
            for e in old['experiments']:
                if not e['runs']:
                    continue
                new_runs = {r['id']: r for r in incoming.get(e['id'], {}).get('runs', [])}
                for r in e['runs']:
                    if new_runs.get(r['id']) != r:
                        raise ValueError('Recorded runs are immutable. Fork the experiment to change its plan.')
            db.execute('UPDATE workspace SET data=?, revision=? WHERE id=1', (canonical(data), current + 1))
        return current + 1

    def bundle(self):
        state = self.get()
        body = {'schema_version': 1, 'system_id': self.system_id, 'source_revision': state['revision'], 'workspace': state['data']}
        body['sha256'] = hashlib.sha256(canonical(body).encode()).hexdigest()
        return body

    def ingest(self, bundle):
        bundle = copy.deepcopy(bundle)
        checksum = bundle.pop('sha256', '')
        if checksum != hashlib.sha256(canonical(bundle).encode()).hexdigest():
            raise ValueError('Bundle checksum mismatch')
        source = bundle.get('system_id', '')
        if bundle.get('schema_version') != 1 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', source):
            raise ValueError('Unsupported bundle format')
        source_rev = bundle.get('source_revision')
        if not isinstance(source_rev, int) or source_rev < 1:
            raise ValueError('Invalid source revision')
        if source == self.system_id:
            raise ValueError('Cannot ingest this workspace into itself; use a distinct master system ID')
        incoming = validate(bundle['workspace'])
        prefix = source + '::'
        for group in ('experiments', 'platforms', 'adrs'):
            for row in incoming[group]:
                row['id'] = prefix + row['id'] if not row['id'].startswith(prefix) else row['id']
                if group == 'experiments':
                    old_platform = row['platform']
                    row['platform'] = old_platform if old_platform.startswith(prefix) else prefix + old_platform
                    for run in row['runs']:
                        contract = json.loads(run['contract'])
                        if contract.get('platform') == old_platform:
                            contract['platform'] = row['platform']
                            # Preserve JS serialization order used by the qualification contract.
                            run['contract'] = json.dumps(contract, separators=(',', ':'), ensure_ascii=False)
                elif group == 'platforms':
                    row['name'] = source + ' / ' + row['name']
        key = 'ingest:' + source
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
            if previous:
                prior = json.loads(previous[0])
                if source_rev < prior['revision']:
                    raise ValueError('Stale bundle rejected')
                if source_rev == prior['revision']:
                    if checksum == prior['sha256']:
                        return False
                    raise ValueError('Conflicting bundle for an existing source revision')
            raw, revision = db.execute('SELECT data, revision FROM workspace WHERE id=1').fetchone()
            data = json.loads(raw)
            for group in ('experiments', 'platforms', 'adrs'):
                data[group] = [r for r in data[group] if not r['id'].startswith(prefix)] + incoming[group]
            db.execute('UPDATE workspace SET data=?, revision=? WHERE id=1', (canonical(data), revision + 1))
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', (key, canonical({'revision': source_rev, 'sha256': checksum})))
        return True


class LabServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, store, token=None):
        self.store = store
        self.token = token or secrets.token_urlsafe(32)
        self.session = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log credentials, paths, cookies or user experiment data.

    def host_ok(self):
        try:
            host = urlsplit('http://' + self.headers.get('Host', '')).hostname
            return host in ('127.0.0.1', 'localhost', '::1')
        except ValueError:
            return False

    def auth(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get('Cookie', ''))
            return secrets.compare_digest(c['ql_session'].value, self.server.session)
        except (KeyError, ValueError):
            return False

    def reply(self, code, body=b'', mime='application/json', headers=None):
        if isinstance(body, dict):
            body = canonical(body).encode()
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        for k, v in {'Content-Type': mime, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY', **(headers or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0 or length > MAX_BYTES:
            raise ValueError('Request must contain 1 byte to 8 MiB')
        return self.rfile.read(length)

    def do_GET(self):
        if not self.host_ok():
            return self.reply(403, {'error': 'Loopback host required'})
        path = urlsplit(self.path).path
        if path == '/login':
            return self.reply(200, '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unlock Qualification Lab</title><body style="font:16px system-ui;max-width:440px;margin:12vh auto;padding:24px;background:#f6f7f2;color:#21352f"><h1>Qualification Lab</h1><p>Enter the access key printed in your server terminal. Access this page through your SSH tunnel.</p><form method="post" action="/login"><label>Access key <input type="password" name="key" required autocomplete="off" style="width:100%;padding:12px;box-sizing:border-box;margin:15px 0"></label><button style="background:#246854;color:white;border:0;padding:12px 20px">Unlock local workspace</button></form></body></html>', 'text/html; charset=utf-8')
        if not self.auth():
            return self.reply(401, {'error': 'Unlock the local workspace at /login.'}) if path.startswith('/api/') else self.reply(303, b'', headers={'Location': '/login'})
        if path == '/api/workspace':
            return self.reply(200, self.server.store.get())
        if path == '/api/bundle':
            return self.reply(200, self.server.store.bundle())
        target = (ROOT / 'web' / (path.lstrip('/') or 'index.html')).resolve()
        if not target.is_relative_to((ROOT / 'web').resolve()) or not target.is_file():
            return self.reply(404, {'error': 'Not found'})
        self.reply(200, target.read_bytes(), mimetypes.guess_type(str(target))[0] or 'application/octet-stream')

    def write_allowed(self):
        if not self.host_ok():
            return False
        origin = self.headers.get('Origin')
        return not origin or origin == 'http://' + self.headers.get('Host', '')

    def do_POST(self):
        if not self.write_allowed() or urlsplit(self.path).path != '/login':
            return self.reply(403, {'error': 'Request rejected'})
        try:
            fields = parse_qs(self.read_body().decode())
            key = fields.get('key', [''])[0]
        except (ValueError, UnicodeError):
            return self.reply(400, {'error': 'Invalid login'})
        if not secrets.compare_digest(key, self.server.token):
            return self.reply(401, {'error': 'Incorrect access key'})
        self.reply(303, b'', headers={'Location': '/', 'Set-Cookie': 'ql_session=' + self.server.session + '; HttpOnly; SameSite=Strict; Path=/'})

    def do_PUT(self):
        if not self.write_allowed():
            return self.reply(403, {'error': 'Origin or host rejected'})
        if not self.auth():
            return self.reply(401, {'error': 'Unlock the local workspace at /login.'})
        if urlsplit(self.path).path != '/api/workspace':
            return self.reply(404, {'error': 'Not found'})
        try:
            body = json.loads(self.read_body())
            revision = self.server.store.put(body['data'], body['revision'])
            self.reply(200, {'revision': revision})
        except Conflict as e:
            self.reply(409, {'error': str(e)})
        except (ValueError, KeyError, TypeError, UnicodeError) as e:
            self.reply(400, {'error': 'Invalid workspace: ' + str(e)})
        except sqlite3.Error:
            self.reply(503, {'error': 'Storage unavailable or busy. Check filesystem and retry.'})


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system-id', required=True, help='Stable unique system name, e.g. pilot-a or master')
    parser.add_argument('--data', default=str(Path.home() / '.local/share/qualification-lab/workspace.sqlite'))
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve', help='Start the SSH-local dashboard')
    serve.add_argument('--port', type=int, default=8080)
    export = sub.add_parser('export', help='Export a checksummed system bundle')
    export.add_argument('--output', required=True)
    ingest = sub.add_parser('ingest', help='Ingest one or more source bundles into a master workspace')
    ingest.add_argument('bundles', nargs='+')
    args = parser.parse_args()
    try:
        store = Store(args.data, args.system_id)
        if args.command == 'export':
            path = Path(args.output).expanduser()
            if path.exists():
                raise ValueError('Output exists; choose a new bundle filename')
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x') as f:
                json.dump(store.bundle(), f, indent=2, ensure_ascii=False, allow_nan=False)
                f.write('\n')
            print('Bundle exported to ' + str(path))
        elif args.command == 'ingest':
            for source in args.bundles:
                path = Path(source)
                if path.stat().st_size > MAX_BYTES:
                    raise ValueError('Bundle exceeds 8 MiB')
                changed = store.ingest(json.loads(path.read_text()))
                print(path.name + ': ' + ('ingested' if changed else 'already current'))
        else:
            if not (ROOT / 'web/index.html').is_file():
                raise ValueError('Prebuilt web assets missing; see README build instructions')
            server = LabServer(('127.0.0.1', args.port), store)
            print('Qualification Lab: http://127.0.0.1:' + str(server.server_port) + '/login', flush=True)
            print('Access key (keep private): ' + server.token, flush=True)
            print('Data: ' + str(store.path) + '\nStop with Ctrl-C. Connect through SSH local forwarding.', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
    except (ValueError, OSError, sqlite3.Error) as e:
        parser.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
