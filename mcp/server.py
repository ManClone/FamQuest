"""FamQuest MCP: authenticated, draft-only quest proposal service.

No bank access, no FamQuest parent-session impersonation, no quest publication.
"""
import hmac
import base64
import html
import os
import sqlite3
from urllib.parse import urlsplit
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
from pydantic import Field

DB_PATH = Path(os.getenv("QUEST_DB_PATH", "/data/quests.sqlite3"))
HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8000"))
TOKEN = os.getenv("FAMQUEST_MCP_TOKEN", "")
PARENT_TOKEN = os.getenv("FAMQUEST_PARENT_TOKEN", "")
if len(TOKEN) < 32 or len(PARENT_TOKEN) < 32 or hmac.compare_digest(TOKEN, PARENT_TOKEN):
    raise RuntimeError("Zwei unterschiedliche Tokens mit mindestens 32 Zeichen erforderlich")

mcp = FastMCP("FamQuest Quest Entwürfe", host=HOST, port=PORT, stateless_http=True, json_response=True)


class BearerAuth:
    """Require a shared bearer secret for every HTTP and WebSocket request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        path = scope.get("path", "")
        parent = path.startswith("/parent")
        expected = ("Basic " + base64.b64encode(("parent:" + PARENT_TOKEN).encode()).decode()).encode() if parent else ("Bearer " + TOKEN).encode()
        actual = headers.get(b"authorization", b"")
        if not hmac.compare_digest(actual, expected):
            if scope["type"] == "http":
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"text/plain"),
                                        (b"www-authenticate", b'Basic realm="FamQuest Eltern"' if parent else b"Bearer")]})
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


async def parent_review(request):
    """Minimal parent-only review view; no publishing to FamQuest yet."""
    with database() as db:
        db.row_factory = sqlite3.Row
        rows = [dict(x) for x in db.execute(
            "SELECT id,title,description,points,bonus_cents,recurrence,status FROM quest_proposals ORDER BY id DESC LIMIT 100"
        )]
    parts = ["<h1>Quest-Entwürfe zur Prüfung</h1>",
             "<p>Freigabe bestätigt nur den Entwurf; Veröffentlichung in FamQuest ist noch nicht implementiert.</p>"]
    for q in rows:
        title = html.escape(q["title"])
        desc = html.escape(q["description"])
        parts.append(f"<section><h2>{title}</h2><p>{desc}</p><p>{q['points']} XP · {q['bonus_cents']} Cent vorgeschlagen · Status: {html.escape(q['status'])}</p>")
        if q["status"] == "draft":
            for decision, label in (("approved", "Entwurf freigeben"), ("rejected", "Ablehnen")):
                parts.append(f'<form action="/parent/decide/{q["id"]}/{decision}" method="post"><button>{label}</button></form>')
        parts.append("</section><hr>")
    return HTMLResponse("<!doctype html><html lang='de'><meta charset='utf-8'><title>FamQuest Freigabe</title><body>" + "".join(parts) + "</body></html>")


async def parent_decide(request):
    # Browser Basic authentication is ambient: reject cross-site form submissions.
    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")
    if not origin or urlsplit(origin).netloc != host or urlsplit(origin).scheme not in ("http", "https"):
        return PlainTextResponse("Origin check failed", status_code=403)
    proposal_id = int(request.path_params["proposal_id"])
    decision = request.path_params["decision"]
    if decision not in ("approved", "rejected"):
        return PlainTextResponse("Invalid decision", status_code=400)
    with database() as db:
        result = db.execute(
            "UPDATE quest_proposals SET status=? WHERE id=? AND status='draft'",
            (decision, proposal_id),
        )
        if result.rowcount != 1:
            return PlainTextResponse("Not found or already reviewed", status_code=409)
    return RedirectResponse("/parent", status_code=303)


def build_app():
    # Keep the MCP ASGI app mounted separately. All requests are protected by BearerAuth.
    from starlette.applications import Starlette
    from starlette.routing import Mount
    return Starlette(routes=[
        Route("/parent", parent_review, methods=["GET"]),
        Route("/parent/decide/{proposal_id:int}/{decision:str}", parent_decide, methods=["POST"]),
        Mount("/", app=mcp.streamable_http_app()),
    ])


if __name__ == "__main__":
    uvicorn.run(BearerAuth(build_app()), host=HOST, port=PORT)
