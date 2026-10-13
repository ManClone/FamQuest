"""Internal service endpoint: only accepts already parent-approved quest proposals."""
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.tasks import apply_task, task_out
from app.config import get_settings
from app.db import get_db
from app.models import Task, QuestImport
from app.schemas import TaskIn

router = APIRouter(tags=["quest-import"])


class QuestImportIn(BaseModel):
    external_id: str = Field(min_length=1, max_length=120)
    task: TaskIn


@router.post("/internal/quest-import", status_code=201)
def import_quest(
    body: QuestImportIn,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
):
    secret = get_settings().quest_import_token
    if not secret or len(secret) < 32 or not authorization or not hmac.compare_digest(
        authorization, "Bearer " + secret
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")
    # Serialize imports to avoid duplicate publication on retries.
    db.execute(__import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(82619503)"))
    existing = db.scalar(select(QuestImport).where(QuestImport.external_id == body.external_id))
    if existing:
        return {"task_id": existing.task_id, "created": False}
    task = Task()
    # Force parent verification of completions, regardless of client input.
    payload = body.task.model_copy(update={"needs_approval": True, "extra": True})
    apply_task(db, task, payload)
    db.add(task)
    db.flush()
    db.add(QuestImport(external_id=body.external_id, task_id=task.id))
    db.commit()
    return {"task_id": task.id, "created": True}
