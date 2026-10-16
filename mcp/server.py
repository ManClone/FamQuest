"""FamQuest MCP: live API tools with GitHub OAuth and explicit parent mapping."""

import asyncio
import json
import os
import re
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.middleware import Middleware
from gateway import GatewayTransport, parent_id
from key_value.aio.stores.disk import DiskStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from mcp.types import ToolAnnotations


class ParentBoundary(Middleware):
    def __init__(self, mapping):
        self.mapping = mapping

    async def on_call_tool(self, context, call_next):
        parent_id(self.mapping)
        return await call_next(context)

    async def on_list_tools(self, context, call_next):
        parent_id(self.mapping)
        return await call_next(context)


def tool_metadata(route, component):
    read = route.method.upper() == "GET"
    component.annotations = ToolAnnotations(
        readOnlyHint=read,
        destructiveHint=not read,
        idempotentHint=read,
        openWorldHint=False,
    )


def build_server(spec, client, mapping, auth=None):
    names = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            name = (
                method
                + "_"
                + re.sub(r"[^a-zA-Z0-9]+", "_", path.removeprefix("/api/")).strip("_")
            )
            names[operation["operationId"]] = name
    server = FastMCP.from_openapi(
        spec,
        client,
        name="FamQuest",
        auth=auth,
        mcp_names=names,
        mcp_component_fn=tool_metadata,
        instructions=(
            "Manage the linked family's tasks, routines, household, weekly plan, meals, shopping "
            "and rewards. Read current definitions and member IDs before planning. All API "
            "parameters and validation apply unchanged. Use the same X-MCP-Request-Key for "
            "retries, a fresh UUID for a new action. Do not claim success on an API error. "
            "Child approvals require an explicit decision by the parent; never approve them "
            "automatically. Money, banking, credentials and account management are excluded. "
            "The Household category is populated by household chores, never create it as a routine."
        ),
    )
    server.add_middleware(ParentBoundary(mapping))

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    async def get_connected_parent() -> dict:
        """Show the linked parent profile; use this to verify which account is connected."""
        response = await client.get("/api/profile")
        response.raise_for_status()
        return {"parent_user_id": parent_id(mapping), "profile": response.json()}

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    async def get_pending_notifications() -> dict:
        """Read pending child approvals and household reminders. Does not send notifications.

        Suitable for reminder checks: notify only when something is pending. Failures must
        be reported as unavailable, never as an empty queue.
        """
        approvals, household = await asyncio.gather(
            client.get("/api/approvals"),
            client.get("/api/chores"),
        )
        approvals.raise_for_status()
        household.raise_for_status()
        plan = household.json()
        due = [
            c
            for c in plan.get("chores", [])
            if c["level"] == "due" and not c["done_today"]
        ]
        todos = [t for t in plan.get("todos", []) if not t["done"]]
        return {
            "approvals": approvals.json(),
            "due_household": due,
            "open_todos": todos,
            "has_pending": bool(approvals.json() or due or todos),
        }

    return server


async def main():
    os.umask(0o077)
    mapping = json.loads(os.environ["FAMQUEST_GITHUB_PARENTS"])
    if not mapping or any(
        not k.isdecimal() or type(v) is not int or v < 1 for k, v in mapping.items()
    ):
        raise ValueError(
            "Map immutable numeric GitHub user IDs to existing FamQuest parent user IDs."
        )
    secret = os.environ["FAMQUEST_SERVICE_TOKEN"]
    if len(secret) < 32:
        raise ValueError(
            "FAMQUEST_SERVICE_TOKEN must contain at least 32 random characters."
        )
    base = os.environ.get("FAMQUEST_API_URL", "http://app:8080")
    data = Path(os.environ.get("MCP_DATA_DIR", "/data"))
    auth = GitHubProvider(
        client_id=os.environ["GITHUB_CLIENT_ID"],
        client_secret=os.environ["GITHUB_CLIENT_SECRET"],
        base_url=os.environ["MCP_PUBLIC_URL"],
        required_scopes=["read:user"],
        jwt_signing_key=os.environ["MCP_JWT_SIGNING_KEY"],
        client_storage=FernetEncryptionWrapper(
            DiskStore(directory=data / "oauth"),
            fernet=Fernet(os.environ["MCP_STORAGE_ENCRYPTION_KEY"]),
        ),
    )
    async with httpx.AsyncClient(
        base_url=base, timeout=30, follow_redirects=False
    ) as bootstrap:
        response = await bootstrap.get(
            "/api/internal/mcp/schema",
            headers={
                "Authorization": "Bearer " + secret,
                "X-FamQuest-Parent-ID": str(next(iter(mapping.values()))),
            },
        )
        response.raise_for_status()
        spec = response.json()
    transport = GatewayTransport(secret, mapping, data / "audit.sqlite3")
    async with httpx.AsyncClient(
        base_url=base, transport=transport, timeout=30
    ) as client:
        server = build_server(spec, client, mapping, auth)
        await server.run_async(transport="http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    asyncio.run(main())
