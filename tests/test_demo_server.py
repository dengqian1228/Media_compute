"""Exercise real HTTP run/replay with archived RGB and gray photographs."""
import base64
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from http.client import HTTPConnection

from scripts.demo_server import DemoServer, ROOT


class DemoServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        target = cls.root / 'data/structure_smoothing/inputs'
        target.mkdir(parents=True)
        for name in ['beach.png', 'brick_window_gray.png', 'sunflower.png']:
            shutil.copy2(ROOT / 'data/structure_smoothing/inputs' / name, target / name)
        (cls.root / '.git').mkdir()
        (cls.root / '.git/config').write_text('private')
        (cls.root / 'AI_LOG.md').write_text('AI execution record')
        (cls.root / 'README.md').write_text('Demo instructions')
        (cls.root / 'private.txt').write_text('not public')
        (cls.root / 'docs').mkdir()
        (cls.root / 'docs/demo_interactive.html').write_text('<!doctype html><title>Demo</title>')
        cls.server = DemoServer(0, cls.root)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, data=None, headers=None):
        headers = headers or {}
        if data is not None:
            headers = {'Content-Type': 'application/json', **headers}
        conn = HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=30)
        try:
            conn.request('GET' if data is None else 'POST', path,
                         body=None if data is None else json.dumps(data).encode(), headers=headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_rgb_run_saves_outputs_and_replays(self):
        code, result = self.request('/api/run', {'sample': 'beach', 'lambda': .008, 'kappa': 2})
        self.assertEqual(code, 200, result)
        self.assertEqual(result['record']['input']['mode'], 'RGB')
        for value in result['files'].values():
            self.assertTrue((self.root / value.lstrip('/')).is_file())
        code, replay = self.request('/api/replay', {'record_path': result['record_path']})
        self.assertEqual(code, 200, replay)
        self.assertTrue(replay['passed'])
        self.assertEqual(replay['comparison']['different_pixel_count'], 0)
        self.assertLessEqual(replay['comparison']['max_float_abs_error'], 1e-12)

    def test_gray_upload_keeps_original_bytes_and_replays(self):
        raw = (self.root / 'data/structure_smoothing/inputs/brick_window_gray.png').read_bytes()
        code, result = self.request('/api/run', {'file': {'name': '../../brick.png', 'base64': base64.b64encode(raw).decode()}, 'lambda': .02, 'kappa': 1.5})
        self.assertEqual(code, 200, result)
        self.assertEqual(result['record']['input']['mode'], 'L')
        saved = self.root / result['files']['input'].lstrip('/')
        self.assertEqual(saved.read_bytes(), raw)
        code, replay = self.request('/api/replay', {'record_path': result['record_path']})
        self.assertEqual(code, 200, replay)
        self.assertTrue(replay['passed'])

    def test_cross_origin_hidden_paths_and_bad_records_rejected(self):
        for path in ['/.git/config', '/%2e%2e/README.md', '/docs/../../.git/config']:
            code, result = self.request(path)
            self.assertIn(code, (403, 404), result)
        code, _ = self.request('/api/run', {'sample': 'beach'}, {'Origin': 'https://example.org'})
        self.assertEqual(code, 403)
        code, _ = self.request('/api/status', headers={'Host': 'evil.example'})
        self.assertEqual(code, 403)
        for path in ['../outside/run.json', '/tmp/run.json', 'data/run.json']:
            code, _ = self.request('/api/replay', {'record_path': path})
            self.assertEqual(code, 400)
        code, _ = self.request('/api/run', {'sample': 'beach', 'kappa': 1})
        self.assertEqual(code, 400)
        code, _ = self.request('/api/run', {'file': {'base64': 'not an image'}})
        self.assertEqual(code, 400)

    def test_only_explicit_root_documents_are_public(self):
        for name, expected, content in [
            ('AI_LOG.md', 200, b'AI execution record'),
            ('README.md', 200, b'Demo instructions'),
            ('private.txt', 404, None),
            ('.git/config', 403, None),
        ]:
            conn = HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
            try:
                conn.request('GET', '/' + name)
                response = conn.getresponse()
                body = response.read()
                self.assertEqual(response.status, expected)
                if content is not None:
                    self.assertEqual(body, content)
            finally:
                conn.close()

    def test_concurrent_compute_is_rejected(self):
        self.server.compute_lock.acquire()
        try:
            code, _ = self.request('/api/run', {'sample': 'beach'})
            self.assertEqual(code, 409)
        finally:
            self.server.compute_lock.release()
        code, status = self.request('/api/status')
        self.assertEqual(code, 200)
        self.assertTrue(status['available'])

    def test_external_link_can_open_demo_but_cannot_call_api(self):
        navigation = {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate',
                      'Sec-Fetch-Dest': 'document', 'Sec-Fetch-User': '?1'}
        for path in ['/', '/docs/demo_interactive.html']:
            conn = HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
            try:
                conn.request('GET', path, headers=navigation)
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn(b'<title>Demo</title>', response.read())
            finally:
                conn.close()
        for headers in [
            navigation,
            {**navigation, 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty'},
            {**navigation, 'Sec-Fetch-Dest': 'iframe'},
        ]:
            code, _ = self.request('/api/run', {'sample': 'beach'}, headers)
            self.assertEqual(code, 403)
            code, _ = self.request('/api/replay', {'record_path': 'anything'}, headers)
            self.assertEqual(code, 403)
            code, _ = self.request('/api/status', headers=headers)
            self.assertEqual(code, 403)
        for headers in [
            {**navigation, 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty'},
            {**navigation, 'Sec-Fetch-Dest': 'iframe'},
            {**navigation, 'Host': 'evil.example'},
        ]:
            code, _ = self.request('/', headers=headers)
            self.assertEqual(code, 403)
        code, status = self.request('/api/status', headers={
            'Origin': self.url, 'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors'})
        self.assertEqual(code, 200)
        self.assertTrue(status['available'])


if __name__ == '__main__':
    unittest.main()
