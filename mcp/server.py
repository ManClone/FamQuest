"""FamQuest MCP: authenticated, draft-only quest proposal service.

No bank access, no FamQuest parent-session impersonation, no quest publication.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

DB_PATH = Path(os.getenv("QUEST_DB_PATH", "/data/quests.sqlite3"))
HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8000"))
mcp = FastMCP("FamQuest Quest Entwürfe", host=HOST, port=PORT, stateless_http=True, json_response=True)


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
    # Bind only to a trusted private network until OAuth / reverse-proxy auth is configured.
    mcp.run(transport="streamable-http")
