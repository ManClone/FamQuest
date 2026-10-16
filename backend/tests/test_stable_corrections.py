from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models import PenaltyReversal, PointTransaction, User
from tests.conftest import csrf
from tests.test_personal_access import add_person
from tests.test_points import book_manually, history


def test_existing_compensation_is_linked_without_another_refund(client, parent, lena):
    book_manually(client, parent, lena, 10)
    book_manually(client, parent, lena, -1, "Test penalty")
    original = history(client, lena)["transactions"][0]["id"]
    book_manually(client, parent, lena, 1, "Test compensation")
    compensation = history(client, lena)["transactions"][0]["id"]
    path = f"/api/members/{lena}/penalties/{original}/reverse"
    assert client.post(path, json={"reason": "Review"}, headers=csrf(parent)).status_code == 409
    assert history(client, lena)["total"] == 10
    body = {"reason": "Linked after parent review", "existing_compensation_id": compensation}
    first = client.post(path, json=body, headers=csrf(parent))
    assert first.status_code == 200, first.text
    assert first.json()["refund_transaction_id"] == compensation
    # Both routes share a single audit and never double-refund.
    other = f"/api/members/{lena}/points/{original}/reverse"
    assert client.post(other, json=body, headers=csrf(parent)).json() == first.json()
    assert history(client, lena)["total"] == 10
    entries = {t["id"]: t for t in history(client, lena)["transactions"]}
    assert entries[original]["reversed_at"]
    assert entries[compensation]["compensates_transaction_id"] == original
    assert (
        client.post(
            f"/api/members/{lena}/points/{compensation}/reverse",
            json={"reason": "Double correction"},
            headers=csrf(parent),
        ).status_code
        == 409
    )


@pytest.mark.parametrize("amount", [4, -4])
def test_manual_corrections_concurrently_apply_once(client, parent, lena, amount):
    book_manually(client, parent, lena, 20)
    book_manually(client, parent, lena, amount)
    entry = history(client, lena)["transactions"][0]["id"]
    path = f"/api/members/{lena}/points/{entry}/reverse"
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies = list(
            pool.map(
                lambda _: client.post(path, json={"reason": "Correction"}, headers=csrf(parent)),
                range(4),
            )
        )
    assert [r.status_code for r in replies] == [200] * 4
    assert all(r.json() == replies[0].json() for r in replies)
    assert history(client, lena)["total"] == 20
    with SessionLocal() as db:
        reversal = db.get(PenaltyReversal, entry)
        assert db.get(PointTransaction, reversal.refund_transaction_id).kind == "manual_reversed"


def test_credit_reversal_cannot_overdraw_and_mcp_requires_parent_confirmation(
    client, parent, monkeypatch
):
    from app.config import get_settings

    member, credentials = add_person(client, parent, "Tim", "blue")
    book_manually(client, parent, member, 5)
    credit = history(client, member)["transactions"][0]["id"]
    book_manually(client, parent, member, -4)
    path = f"/api/members/{member}/points/{credit}/reverse"
    assert client.post(path, json={"reason": "Correction"}, headers=csrf(parent)).status_code == 409
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        assert child.post(path, json={"reason": "Self"}, headers=csrf(me)).status_code == 403
    with SessionLocal() as db:
        owner = db.scalar(select(User.id).where(User.role == "admin"))
    monkeypatch.setattr(get_settings(), "mcp_service_token", "s" * 40)
    headers = {"Authorization": "Bearer " + "s" * 40, "X-FamQuest-Parent-ID": str(owner)}
    denied = client.post(path, json={"reason": "Correction"}, headers=headers)
    assert denied.json()["code"] == "mcp.parent_confirmation_required"
    assert history(client, member)["total"] == 1
