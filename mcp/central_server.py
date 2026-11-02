"""Opt-in central-family MCP resource server. Legacy entrypoint stays unchanged."""

import asyncio
import os
import time
from urllib.parse import urlsplit

import httpx
from fastmcp.server.auth import AccessToken, RemoteAuthProvider, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import AnyHttpUrl
from server import build_server

SCOPE = "famquest:parent"


def central_parent() -> int:
    token = get_access_token()
    if token is None or SCOPE not in token.scopes:
        raise PermissionError("A current FamQuest parent authorization is required.")
    actor = token.claims.get("parent_user_id")
    if type(actor) is not int or actor < 1:
        raise PermissionError("A family-local parent mapping is required.")
    return actor


class CentralVerifier(TokenVerifier):
    def __init__(self, client, resource):
        super().__init__(required_scopes=[SCOPE])
        self.client = client
        self.resource = resource

    async def verify_token(self, token):
        if not token or len(token) > 512:
            return None
        try:
            response = await self.client.get(
                "/api/internal/mcp/context",
                headers={"authorization": "Bearer " + token},
            )
            if response.status_code != 200:
                return None
            data = response.json()
            for field in ("identity_id", "tenant_id", "parent_user_id", "expires_at"):
                if type(data.get(field)) is not int or data[field] < 1:
                    return None
            if (
                data.get("resource") != self.resource
                or data.get("scopes") != [SCOPE]
                or data.get("role") not in {"admin", "parent"}
                or data["expires_at"] <= time.time()
                or not isinstance(data.get("client_id"), str)
                or not data["client_id"]
            ):
                return None
            return AccessToken(
                token=token,
                client_id=data["client_id"],
                scopes=[SCOPE],
                expires_at=data["expires_at"],
                resource=self.resource,
                subject=str(data["identity_id"]),
                claims={
                    "sub": str(data["identity_id"]),
                    "tenant_id": data["tenant_id"],
                    "parent_user_id": data["parent_user_id"],
                },
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            # No cache or legacy-token fallback when the registry is unavailable.
            return None


class CentralTransport(httpx.AsyncBaseTransport):
    def __init__(self, upstream=None):
        self.upstream = upstream or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        central_parent()
        token = get_access_token()
        request.headers.pop("cookie", None)
        request.headers.pop("x-famquest-parent-id", None)
        request.headers["authorization"] = "Bearer " + token.token
        if request.method not in {"GET", "POST", "PUT", "DELETE"}:
            return httpx.Response(403, json={"code": "mcp.operation_forbidden"})
        return await self.upstream.handle_async_request(request)

    async def aclose(self):
        await self.upstream.aclose()


async def main():
    os.umask(0o077)
    public = os.environ["FAMQUEST_PUBLIC_URL"].rstrip("/")
    parsed = urlsplit(public)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "FAMQUEST_PUBLIC_URL must be the configured HTTPS application origin."
        )
    # Exact public origin also satisfies the backend's host/HTTPS boundary.
    async with httpx.AsyncClient(
        base_url=public, timeout=15, follow_redirects=False
    ) as control:
        result = await control.get("/.well-known/famquest-mcp-tools")
        result.raise_for_status()
        spec = result.json()
        if any(
            set(operations) - {"get", "post", "put", "delete"}
            for operations in spec["paths"].values()
        ):
            raise ValueError("Central tool schema contains unexpected operations.")
        auth = RemoteAuthProvider(
            token_verifier=CentralVerifier(control, public + "/mcp"),
            authorization_servers=[AnyHttpUrl(public)],
            base_url=public,
            resource_name="FamQuest",
        )
        async with httpx.AsyncClient(
            base_url=public,
            transport=CentralTransport(),
            timeout=30,
            follow_redirects=False,
        ) as client:
            server = build_server(
                spec, client, None, auth, resolve_parent=central_parent
            )
            await server.run_async(transport="http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    asyncio.run(main())
