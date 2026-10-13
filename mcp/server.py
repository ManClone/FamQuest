"""FamQuest MCP: authenticated, draft-only quest proposal service.

No bank access, no FamQuest parent-session impersonation, no quest publication.
"""
import hmac
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
import uvicorn
from pydantic import Field

DB_PATH = Path(os.getenv("QUEST_DB_PATH", "/data/quests.sqlite3"))
HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8000"))
TOKEN = os.getenv("FAMQUEST_MCP_TOKEN", "")
if len(TOKEN) < 32:
    raise RuntimeError("FAMQUEST_MCP_TOKEN muss mindestens 32 Zeichen lang sein")

mcp = FastMCP("FamQuest Quest Entwürfe", host=HOST, port=PORT, stateless_http=True, json_response=True)


class BearerAuth:
    """Require a shared bearer secret for every HTTP and WebSocket request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        expected = ("Bearer " + TOKEN).encode("utf-8")
        actual = headers.get(b"authorization", b"")
        if not hmac.compare_digest(actual, expected):
            if scope["type"] == "http":
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"text/plain"),
                                        (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b"Unauthorized"})
            else:
                await send({"type": "websocket.close", "code": 1008})
            return
        await self.app(scope, receive, send)


@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    try:
        con.execute("PRAGMA busy_timeout=10000")
        con.execute("""CREATE TABLE IF NOT EXISTS quest_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, description TEXT NOT NULL,
            points INTEGER NOT NULL, bonus_cents INTEGER NOT NULL,
            recurrence TEXT NOT NULL, created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft'
        )""")
        yield con
        con.commit()
    finally:
        con.close()


@mcp.tool()
def propose_quest(
    title: str = Field(min_length=1, max_length=100),
    description: str = Field(min_length=1, max_length=500),
    points: int = Field(ge=0, le=1000),
    bonus_cents: int = Field(ge=0, le=10000),
    recurrence: Literal["once", "daily", "weekly"] = "once",
) -> dict:
    """Speichert einen Quest-Entwurf für Tim. Veröffentlicht keine Aufgabe und bucht kein Geld.

    bonus_cents sind Euro-Cent als unverbindlicher Vorschlag für Eltern.
    """
    title = title.strip()
    description = description.strip()
    if not title or not description:
        raise ValueError("Titel und Beschreibung dürfen nicht leer sein")
    with database() as db:
        cursor = db.execute(
            "INSERT INTO quest_proposals (title,description,points,bonus_cents,recurrence,created_at) VALUES (?,?,?,?,?,?)",
            (title, description, points, bonus_cents, recurrence, datetime.now(timezone.utc).isoformat()),
        )
        return {"id": cursor.lastrowid, "status": "draft", "published": False,
                "message": "Nur Entwurf; Elternfreigabe und FamQuest-Veröffentlichung folgen."}


@mcp.tool()
def list_quest_proposals() -> list[dict]:
    """Zeigt Quest-Entwürfe an, noch nicht in FamQuest veröffentlicht."""
    with database() as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            "SELECT id,title,description,points,bonus_cents,recurrence,created_at,status FROM quest_proposals ORDER BY id DESC LIMIT 100"
        )]


if __name__ == "__main__":
    uvicorn.run(BearerAuth(mcp.streamable_http_app()), host=HOST, port=PORT)
