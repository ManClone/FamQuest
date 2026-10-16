from fastapi import APIRouter

from app.auth import DbSession, ParentSession
from app.maintenance import consistency_report

router = APIRouter(tags=["maintenance"])


@router.get("/maintenance/consistency")
def get_consistency_report(_: ParentSession, db: DbSession) -> dict:
    """Inspect suspected legacy data. Never changes family records or books corrections."""
    return consistency_report(db)
