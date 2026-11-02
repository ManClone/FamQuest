"""Parent-approved household bonus; frozen cents and a separate journal namespace."""

from sqlalchemy import select

from app.errors import ApiError
from app.models import FamilyMember, MoneyTransaction
from app.money import book_money
from app.points import lock_member


def credit_chore_money(db, completion, title):
    if not completion.approved or not completion.money_cents:
        return
    if db.info.get("mcp_request"):
        raise ApiError(403, "mcp.operation_forbidden")
    member = db.get(FamilyMember, completion.member_id)
    if member is None or member.role != "child":
        raise ApiError(409, "money.child_required")
    lock_member(db, member.id)
    if (
        db.scalar(
            select(MoneyTransaction.id).where(
                MoneyTransaction.completion_id == completion.id,
                MoneyTransaction.kind == "chore_completed",
            )
        )
        is not None
    ):
        return
    book_money(db, member.id, completion.money_cents, "chore_completed", title, completion.id)
