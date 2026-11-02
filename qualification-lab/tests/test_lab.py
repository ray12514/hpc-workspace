import copy
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from lab import Store, Conflict, LabServer, canonical

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'a.sqlite', 'pilot-a')
    def tearDown(self):
        self.tmp.cleanup()
    def test_persistence_and_conflict(self):
        state = self.store.get()
        state['data']['experiments'][0]['title'] = 'Reproducible test'
        self.store.put(state['data'], state['revision'])
        self.assertEqual(Store(self.store.path, 'pilot-a').get()['data']['experiments'][0]['title'], 'Reproducible test')
        with self.assertRaises(Conflict):
            self.store.put(state['data'], state['revision'])
        with self.assertRaises(ValueError):
            Store(self.store.path, 'another-system')
    def test_namespaced_import_idempotence_and_stale_rejection(self):
        master = Store(Path(self.tmp.name) / 'master.sqlite', 'master')
        first = self.store.bundle()
        self.assertTrue(master.ingest(first))
        self.assertFalse(master.ingest(first))
        changed = master.get()
        next(e for e in changed['data']['experiments'] if e['id'].startswith('pilot-a::'))['title'] = 'Master edit'
        with self.assertRaises(ValueError):
            master.put(changed['data'], changed['revision'])
        state = self.store.get()
        state['data']['experiments'][0]['title'] = 'Updated source'
        self.store.put(state['data'], state['revision'])
        self.assertTrue(master.ingest(self.store.bundle()))
        rows = [e for e in master.get()['data']['experiments'] if e['id'].startswith('pilot-a::')]
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]['title'], 'Updated source')
        with self.assertRaises(ValueError):
            master.ingest(first)
        bad = copy.deepcopy(first)
        bad['workspace']['experiments'][0]['title'] = 'Tampered'
        with self.assertRaises(ValueError):
            master.ingest(bad)
    def test_immutable_runs_and_invalid_measurements(self):
        state = self.store.get()
        e = state['data']['experiments'][0]
        r = dict(id='synthetic-only', date='2026-01-01',kind='Baseline',samples=[10,11,12],error=0,cost=0,correctness='Pass',recovery='Pass',operations='Pass',artifact='test fixture',config='test fixture',notes='',contract=json.dumps({k:e[k] for k in ('app','input','quality','tolerance','platform','stack','mode')}),planSnapshot='{}')
        e['runs'].append(r)
        revision = self.store.put(state['data'], state['revision'])
        e['runs'][0]['samples'][0] = 1
        with self.assertRaises(ValueError):
            self.store.put(state['data'], revision)
        bad = self.store.get()
        bad['data']['experiments'][1]['tolerance'] = float('nan')
        with self.assertRaises(ValueError):
            self.store.put(bad['data'], bad['revision'])
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'http.sqlite', 'http-pilot')
        self.server = LabServer(('127.0.0.1', 0), self.store, token='synthetic-test-key')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port
        self.cookie = ''
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()
    def request(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        h = dict(headers or {})
        if self.cookie:
            h['Cookie'] = self.cookie
        c.request(method, path, body=body.encode('utf-8') if isinstance(body, str) else body, headers=h)
        r = c.getresponse()
        result = r.status, dict(r.getheaders()), r.read()
        c.close()
        return result
    def login(self):
        status, headers, _ = self.request('POST', '/login', 'key=synthetic-test-key')
        self.assertEqual(status, 303)
        self.cookie = headers['Set-Cookie'].split(';')[0]
    def test_auth_origin_and_conflict(self):
        self.assertEqual(self.request('GET','/api/workspace')[0],401)
        self.assertEqual(self.request('POST','/login','key=wrong')[0],401)
        self.login()
        status, _, body = self.request('GET','/api/workspace')
        self.assertEqual(status,200)
        state = json.loads(body)
        payload = canonical(state)
        self.assertEqual(self.request('PUT','/api/workspace',payload,{'Origin':'https://untrusted.invalid'})[0],403)
        self.assertEqual(self.request('PUT','/api/workspace',payload)[0],200)
        self.assertEqual(self.request('PUT','/api/workspace',payload)[0],409)
        self.assertEqual(self.request('GET','/api/workspace',headers={'Host':'untrusted.invalid'})[0],403)
    def test_assets_and_traversal(self):
        self.login()
        status, _, body = self.request('GET','/')
        self.assertEqual(status,200)
        self.assertIn(b'assets/',body)
        self.assertEqual(self.request('GET','/../lab.py')[0],404)
        self.assertEqual(self.request('GET','/api/bundle')[0],200)

if __name__ == '__main__':
    unittest.main()
