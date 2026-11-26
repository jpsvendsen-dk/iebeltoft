import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.static_assets import CalendarStaticFiles


class StaticAssetCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        (root / 'jul2026').mkdir()
        (root / 'jul2026' / 'example.css').write_text('body{color:red}', encoding='utf-8')
        (root / 'other.css').write_text('body{}', encoding='utf-8')
        app = FastAPI()
        app.mount('/static', CalendarStaticFiles(directory=root))
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def test_versioned_cache_survives_conditional_and_range_requests(self):
        url = '/static/jul2026/example.css?v=18'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'public, max-age=31536000, immutable')
        unchanged = self.client.get(url, headers={'If-None-Match': response.headers['etag']})
        self.assertEqual(unchanged.status_code, 304)
        self.assertEqual(unchanged.headers['cache-control'], response.headers['cache-control'])
        partial = self.client.get(url, headers={'Range': 'bytes=0-3'})
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial.content, b'body')
        self.assertEqual(partial.headers['cache-control'], response.headers['cache-control'])

    def test_cache_scope_and_unversioned_urls(self):
        for suffix in ('', '?v=', '?v=invalid'):
            response = self.client.get('/static/jul2026/example.css' + suffix)
            self.assertEqual(response.headers['cache-control'], 'public, max-age=3600')
        self.assertNotIn('cache-control', self.client.get('/static/other.css?v=1').headers)
        missing = self.client.get('/static/jul2026/missing.css?v=1')
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn('cache-control', missing.headers)
