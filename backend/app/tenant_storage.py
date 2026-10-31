"""Request-local image directories, inherited by FastAPI worker threads."""

from contextvars import ContextVar
from pathlib import Path

from app.config import get_settings

tenant_upload_root: ContextVar[Path | None] = ContextVar("tenant_upload_root", default=None)


def upload_root() -> Path:
    root = tenant_upload_root.get()
    return root if root is not None else get_settings().upload_dir
