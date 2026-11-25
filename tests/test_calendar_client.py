import unittest
from unittest.mock import patch
from starlette.requests import Request
from app.services.calendar_client import client_metadata, valid_ip


class ClientMetadataTests(unittest.TestCase):
    def request(self, **headers):
        return Request({'type': 'http', 'headers': [(k.lower().encode(), v.encode()) for k, v in headers.items()], 'client': ('192.168.1.2', 1234)})

    def test_direct_requests_ignore_forwarded_ip(self):
        with patch.dict('os.environ', {'RENDER': ''}):
            data = client_metadata(self.request(**{'CF-Connecting-IP': '8.8.8.8', 'X-Forwarded-For': '1.1.1.1'}))
        self.assertEqual(data['ip_address'], '192.168.1.2')
        self.assertIsNone(data['device_type'])

    def test_proxy_ipv6_and_device_detection(self):
        with patch.dict('os.environ', {'RENDER': 'true'}):
            data = client_metadata(self.request(**{'CF-Connecting-IP': '2001:4860:4860::8888', 'User-Agent': 'Mozilla Macintosh Mobile Safari/604.1'}))
            self.assertEqual(data['ip_address'], '2001:4860:4860::8888')
            self.assertIn('iPad', data['device_type'])
            data = client_metadata(self.request(**{'X-Forwarded-For': '1.1.1.1, 8.8.8.8, 10.0.0.1', 'User-Agent': 'Android Mobile Chrome/100'}))
            self.assertEqual(data['ip_address'], '8.8.8.8')
            self.assertIn('Android-mobil', data['device_type'])
        self.assertIsNone(valid_ip('invalid'))
        self.assertIsNone(valid_ip('fe80::1%eth0'))
