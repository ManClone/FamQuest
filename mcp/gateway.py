"""Per-parent API transport with persistent write deduplication and audit trail."""

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import httpx
from fastmcp.server.dependencies import get_access_token


def parent_id(mapping: dict[str, int]) -> int:
    token = get_access_token()
    subject = str(token.claims.get("sub", "")) if token else ""
    if subject not in mapping:
        raise PermissionError("This GitHub account is not linked to a FamQuest parent.")
    return mapping[subject]


class GatewayTransport(httpx.AsyncBaseTransport):
    def __init__(self, token, mapping, database: Path, upstream=None):
        self.token = token
        self.mapping = mapping
        self.database = database
        self.upstream = upstream or httpx.AsyncHTTPTransport()
        database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS actions (
                parent_id INTEGER NOT NULL, request_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL,
                status INTEGER, response BLOB, content_type TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT, PRIMARY KEY(parent_id, request_key))""")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    async def handle_async_request(self, request):
        owner = parent_id(self.mapping)
        request.headers["Authorization"] = "Bearer " + self.token
        request.headers["X-FamQuest-Parent-ID"] = str(owner)
        request.headers.pop("cookie", None)
        if request.method == "GET":
            return await self.upstream.handle_async_request(request)
        key = request.headers.get("X-MCP-Request-Key", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
            return httpx.Response(422, json={"code": "mcp.request_key_required"})
        body = await request.aread()
        fingerprint = hashlib.sha256(
            request.method.encode() + str(request.url).encode() + body
        ).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT fingerprint,status,response,content_type FROM actions "
                "WHERE parent_id=? AND request_key=?",
                (owner, key),
            ).fetchone()
            if row:
                if row[0] != fingerprint:
                    return httpx.Response(409, json={"code": "mcp.request_key_reused"})
                if row[1] is None:
                    return httpx.Response(
                        409, json={"code": "mcp.outcome_unknown_check_state"}
                    )
                return httpx.Response(
                    row[1], content=row[2], headers={"content-type": row[3]}
                )
            db.execute(
                "INSERT INTO actions(parent_id,request_key,fingerprint,method,path) VALUES(?,?,?,?,?)",
                (owner, key, fingerprint, request.method, request.url.path),
            )
        # A network error/crash leaves an uncertain record. Never silently repeat a write.
        response = await self.upstream.handle_async_request(request)
        content = await response.aread()
        content_type = response.headers.get("content-type", "application/json")
        with self.connect() as db:
            db.execute(
                "UPDATE actions SET status=?,response=?,content_type=?,finished_at=CURRENT_TIMESTAMP "
                "WHERE parent_id=? AND request_key=?",
                (response.status_code, content, content_type, owner, key),
            )
        return httpx.Response(
            response.status_code,
            content=content,
            headers={"content-type": content_type},
        )

    async def aclose(self):
        await self.upstream.aclose()
