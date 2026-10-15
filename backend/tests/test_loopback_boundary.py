"""Network-free ASGI checks for RepoPilot's unauthenticated local-only boundary."""
import unittest
from unittest.mock import patch

import httpx
from app import app, is_loopback_client


class LoopbackBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def _request(self, host, route="/api/repositories", headers=None):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(host, 43210)),
            base_url="http://127.0.0.1:8000",
        ) as client:
            return await client.get(route, headers=headers or {})

    def test_only_numeric_loopback_peers_allowed(self):
        for host in ("127.0.0.1", "127.5.4.3", "::1", "::ffff:127.0.0.1"):
            with self.subTest(host=host):
                self.assertTrue(is_loopback_client(host))
        for host in ("8.8.8.8", "192.168.1.1", "172.17.0.2", "::ffff:8.8.8.8",
                     "0.0.0.0", "localhost", "localhost.localdomain", "", None):
            with self.subTest(host=host):
                self.assertFalse(is_loopback_client(host))

    async def test_remote_clients_cannot_access_health_or_repositories(self):
        for host in ("192.168.1.5", "8.8.8.8", "::ffff:192.168.1.5"):
            with self.subTest(host=host):
                for route in ("/api/health", "/api/repositories", "/openapi.json"):
                    response = await self._request(host, route)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json(), {"detail": "Local API only"})

    async def test_spoofed_forwarded_and_host_headers_do_not_bypass(self):
        response = await self._request("203.0.113.7", headers={
            "Host": "localhost:8000",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
            "Forwarded": "for=127.0.0.1",
        })
        self.assertEqual(response.status_code, 403)

    async def test_local_access_remains_functional(self):
        for host in ("127.0.0.1", "::1"):
            with self.subTest(host=host):
                with patch("app.list_repositories", return_value=[]):
                    response = await self._request(host)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"repositories": [], "count": 0})


if __name__ == "__main__":
    unittest.main()
