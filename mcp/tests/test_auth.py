"""MCP account boundary and persistent retry tests; no live GitHub calls."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from gateway import GatewayTransport, parent_id


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_are_parent_scoped_and_conflicts_fail_closed(self):
        calls = []

        async def handler(request):
            calls.append(request)
            return httpx.Response(201, json={"id": len(calls)})

        with tempfile.TemporaryDirectory() as folder:
            transport = GatewayTransport(
                "s" * 40,
                {"10": 1},
                Path(folder) / "audit.db",
                httpx.MockTransport(handler),
            )
            async with httpx.AsyncClient(
                base_url="http://backend", transport=transport
            ) as client:
                with patch("gateway.parent_id", return_value=1):
                    headers = {"X-MCP-Request-Key": "a" * 32}
                    first = await client.post(
                        "/api/tasks", json={"title": "Read"}, headers=headers
                    )
                    retry = await client.post(
                        "/api/tasks", json={"title": "Read"}, headers=headers
                    )
                    conflict = await client.post(
                        "/api/tasks", json={"title": "Run"}, headers=headers
                    )
                    self.assertEqual(first.json(), retry.json())
                    self.assertEqual(conflict.status_code, 409)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0].headers["X-FamQuest-Parent-ID"], "1")
                with patch("gateway.parent_id", return_value=2):
                    await client.post(
                        "/api/tasks", json={"title": "Read"}, headers=headers
                    )
                self.assertEqual(len(calls), 2)

    async def test_missing_key_and_uncertain_outcome_are_not_replayed(self):
        calls = []

        async def handler(request):
            calls.append(request)
            raise httpx.ConnectError("offline")

        with tempfile.TemporaryDirectory() as folder:
            transport = GatewayTransport(
                "s" * 40, {}, Path(folder) / "audit.db", httpx.MockTransport(handler)
            )
            async with httpx.AsyncClient(
                base_url="http://backend", transport=transport
            ) as client:
                with patch("gateway.parent_id", return_value=1):
                    response = await client.post("/api/tasks")
                    self.assertEqual(response.status_code, 422)
                    headers = {"X-MCP-Request-Key": "b" * 32}
                    with self.assertRaises(httpx.ConnectError):
                        await client.post("/api/tasks", headers=headers)
                    retry = await client.post("/api/tasks", headers=headers)
                    self.assertEqual(retry.status_code, 409)
                    self.assertEqual(len(calls), 1)

    def test_unknown_and_missing_github_identity_are_denied(self):
        with (
            patch("gateway.get_access_token", return_value=None),
            self.assertRaises(PermissionError),
        ):
            parent_id({"10": 1})
        from types import SimpleNamespace

        with (
            patch(
                "gateway.get_access_token",
                return_value=SimpleNamespace(claims={"sub": "11"}),
            ),
            self.assertRaises(PermissionError),
        ):
            parent_id({"10": 1})
        with patch(
            "gateway.get_access_token",
            return_value=SimpleNamespace(claims={"sub": "10"}),
        ):
            self.assertEqual(parent_id({"10": 1}), 1)


if __name__ == "__main__":
    unittest.main()
