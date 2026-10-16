from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import PenaltyReversal, PointTransaction, User
from tests.conftest import csrf
from tests.test_personal_access import add_person
from tests.test_points import book_manually, history


def test_penalty_refund_preserves_original_and_only_refunds_once(client, parent, now, monkeypatch):
    child_id, credentials = add_person(client, parent, "Tim", "blue")
    other_id, _ = add_person(client, parent, "Tom", "green")
    book_manually(client, parent, child_id, 20)
    book_manually(client, parent, child_id, -4, "Original reason")
    record = history(client, child_id)["transactions"][0]
    path = f"/api/members/{child_id}/penalties/{record['id']}/reverse"
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        assert child.get(f"/api/members/{child_id}/penalties").status_code == 403
        assert child.post(path, json={"reason": "Self"}, headers=csrf(me)).status_code == 403
    assert client.post(path, json={"reason": " "}, headers=csrf(parent)).status_code == 422
    assert (
        client.post(
            f"/api/members/{other_id}/penalties/{record['id']}/reverse",
            json={"reason": "Wrong"},
            headers=csrf(parent),
        ).status_code
        == 404
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    path, json={"reason": "Accidental deduction"}, headers=csrf(parent)
                ),
                range(4),
            )
        )
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json() == responses[0].json() for r in responses)
    assert history(client, child_id)["total"] == 20
    assert (
        client.post(path, json={"reason": "Changed retry"}, headers=csrf(parent)).json()
        == responses[0].json()
    )
    progress = client.get(f"/api/members/{child_id}/progress").json()
    assert progress["latest_deduction_id"] == 0
    assert progress["earned_xp"] == progress["praise_count"] == 0
    penalties = client.get(f"/api/members/{child_id}/penalties").json()["penalties"]
    assert penalties[0]["reason"] == "Original reason"
    assert penalties[0]["reversal_reason"] == "Accidental deduction"
    assert penalties[0]["reversed_at"]
    with SessionLocal() as db:
        original = db.get(PointTransaction, record["id"])
        reversal = db.get(PenaltyReversal, record["id"])
        refund = db.get(PointTransaction, reversal.refund_transaction_id)
        assert original.amount == -4 and original.reason == "Original reason"
        assert refund.amount == 4 and refund.kind == "penalty_reversed"
        assert reversal.created_by_user_id is not None
        owner = db.scalar(select(User.id).where(User.role == "admin"))
    # A credit, refund or reward debit must never become a refundable penalty.
    for row in history(client, child_id)["transactions"]:
        if row["id"] != record["id"]:
            assert (
                client.post(
                    f"/api/members/{child_id}/penalties/{row['id']}/reverse",
                    json={"reason": "Invalid"},
                    headers=csrf(parent),
                ).status_code
                == 409
            )
    monkeypatch.setattr(get_settings(), "mcp_service_token", "s" * 40)
    headers = {"Authorization": "Bearer " + "s" * 40, "X-FamQuest-Parent-ID": str(owner)}
    assert client.get(f"/api/members/{child_id}/penalties", headers=headers).status_code == 200
    assert client.post(path, json={"reason": "Retry"}, headers=headers).status_code == 409
    assert (
        client.post(
            path, json={"reason": "Retry"}, headers={**headers, "X-MCP-Parent-Confirmed": "true"}
        ).status_code
        == 200
    )
