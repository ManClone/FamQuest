"""Serve the built browser app without importing a production application."""

import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

mimetypes.add_type("image/webp", ".webp")


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)
