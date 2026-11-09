"""Individual central bearer verification; no live NAS, accounts or OAuth provider."""

import time
import unittest
from unittest.mock import patch

import httpx
from central_server import SCOPE, CentralTransport, CentralVerifier, central_parent
from fastmcp import Client
from fastmcp.server.auth import AccessToken
from server import build_server

RESOURCE = "https://family.example.invalid/mcp"


def context(**changes):
    return {
        "identity_id": 20,
        "tenant_id": 2,
        "parent_user_id": 1,
        "role": "parent",
        "client_id": "registered",
        "expires_at": int(time.time()) + 300,
        "resource": RESOURCE,
        "scopes": [SCOPE],
        **changes,
    }


class CentralTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_tool_call_uses_individual_parent_context(self):
        observed = []

        def handler(request):
            observed.append(request.headers["authorization"])
            return httpx.Response(200, json={"name": "Henning parent"})

        token = AccessToken(
            token="henning-individual-token",
            client_id="registered",
            scopes=[SCOPE],
            claims={"tenant_id": 2, "parent_user_id": 1},
        )
        spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1"},
            "paths": {},
        }
        async with httpx.AsyncClient(
            base_url="https://family.example.invalid",
            transport=CentralTransport(httpx.MockTransport(handler)),
        ) as api:
            server = build_server(spec, api, None, resolve_parent=central_parent)
            with patch("central_server.get_access_token", return_value=token):
                async with Client(server) as mcp:
                    result = await mcp.call_tool("get_connected_parent")
                    self.assertEqual(result.data["parent_user_id"], 1)
                    self.assertEqual(result.data["profile"]["name"], "Henning parent")
        self.assertEqual(observed, ["Bearer henning-individual-token"])

    async def test_verification_rechecks_registry_and_binds_resource_and_local_actor(
        self,
    ):
        calls = []
        current = context()

        async def handler(request):
            calls.append(request)
            return httpx.Response(200, json=current)

        async with httpx.AsyncClient(
            base_url="https://family.example.invalid",
            transport=httpx.MockTransport(handler),
        ) as client:
            verifier = CentralVerifier(client, RESOURCE)
            token = await verifier.verify_token("individual-token")
            self.assertEqual(token.subject, "20")
            self.assertEqual(token.claims["tenant_id"], 2)
            self.assertEqual(token.claims["parent_user_id"], 1)
            self.assertEqual(
                calls[0].headers["authorization"], "Bearer individual-token"
            )
            for changes in (
                {"role": "child"},
                {"resource": "https://other.invalid/mcp"},
                {"parent_user_id": None},
                {"tenant_id": True},
                {"expires_at": 1},
                {"scopes": []},
                {"client_id": ""},
            ):
                current = context(**changes)
                self.assertIsNone(await verifier.verify_token("individual-token"))
            self.assertEqual(len(calls), 8)

    async def test_denied_unavailable_and_malformed_registry_fail_closed(self):
        for status, data in (
            (401, {}),
            (503, {}),
            (200, []),
            (200, {"tenant_id": "2"}),
        ):
            async with httpx.AsyncClient(
                base_url="https://family.example.invalid",
                transport=httpx.MockTransport(
                    lambda _, status=status, data=data: httpx.Response(
                        status, json=data
                    )
                ),
            ) as client:
                self.assertIsNone(
                    await CentralVerifier(client, RESOURCE).verify_token("token")
                )

        def offline(_):
            raise httpx.ConnectError("unavailable")

        async with httpx.AsyncClient(
            base_url="https://family.example.invalid",
            transport=httpx.MockTransport(offline),
        ) as client:
            self.assertIsNone(
                await CentralVerifier(client, RESOURCE).verify_token("token")
            )

    async def test_transport_forwards_only_current_bearer_for_reads_and_writes(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={"ok": True})

        token = AccessToken(
            token="tenant-two-token",
            client_id="registered",
            scopes=[SCOPE],
            claims={"tenant_id": 2, "parent_user_id": 1},
        )
        with patch("central_server.get_access_token", return_value=token):
            await self.check_forwarding(token, calls, handler)
        with (
            patch("central_server.get_access_token", return_value=None),
            self.assertRaises(PermissionError),
        ):
            central_parent()

    async def test_transport_replaces_inherited_unsupported_response_encodings(self):
        observed = []

        def handler(request):
            observed.append(request.headers["accept-encoding"])
            return httpx.Response(200, json=[{"name": "Eltern mit Umlaut: Jörg"}])

        token = AccessToken(
            token="family-parent-token",
            client_id="registered",
            scopes=[SCOPE],
            claims={"tenant_id": 2, "parent_user_id": 1},
        )
        with patch("central_server.get_access_token", return_value=token):
            async with httpx.AsyncClient(
                base_url="https://family.example.invalid",
                transport=CentralTransport(httpx.MockTransport(handler)),
            ) as client:
                response = await client.get(
                    "/api/members", headers={"accept-encoding": "br, zstd, gzip"}
                )
                self.assertEqual(response.json()[0]["name"], "Eltern mit Umlaut: Jörg")
        self.assertEqual(observed, ["gzip, deflate"])

    async def check_forwarding(self, token, calls, handler):
        async with httpx.AsyncClient(
            base_url="https://family.example.invalid",
            transport=CentralTransport(httpx.MockTransport(handler)),
        ) as client:
            response = await client.get(
                "/api/profile",
                headers={
                    "cookie": "legacy=session",
                    "x-famquest-parent-id": "88",
                    "authorization": "Bearer global-token",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                calls[0].headers["authorization"], "Bearer tenant-two-token"
            )
            self.assertNotIn("cookie", calls[0].headers)
            self.assertNotIn("x-famquest-parent-id", calls[0].headers)
            self.assertEqual((await client.post("/api/tasks")).status_code, 200)
            self.assertEqual(
                calls[1].headers["authorization"], "Bearer tenant-two-token"
            )
            self.assertEqual((await client.patch("/api/tasks")).status_code, 403)
            self.assertEqual(len(calls), 2)
