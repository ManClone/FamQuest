"""Household euros stay independent of stars, with parent review and reversible snapshots."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import MoneyTransaction, User
from tests.conftest import SATURDAY, csrf
from tests.test_activity import activity, restore_row
from tests.test_adult_chore_credits import parent_member
from tests.test_chores import add_chore, add_room, done
from tests.test_mcp_access import service_headers
from tests.test_personal_access import add_person
from tests.test_today import add_task, complete


def money(client, member):
    return client.get(f"/api/members/{member}/money").json()["bonus_cents"]


def paid_chore(client, parent, child, **extra):
    return add_chore(
        client,
        parent,
        add_room(client, parent)["id"],
        child_enabled=True,
        child_member_ids=[child],
        money_cents=50,
        **extra,
    )


def submit_child(client, credentials, chore, key="a" * 32):
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        response = child.put(
            f"/api/chores/mine/{chore['id']}/done", json={"request_key": key}, headers=csrf(me)
        )
        assert response.status_code == 200, response.text


@pytest.mark.parametrize("points", [0, 2])
def test_bonus_waits_for_parent_then_restores_original_amount(client, parent, now, points):
    member, credentials = add_person(client, parent, "Lena", "purple")
    chore = paid_chore(client, parent, member, child_xp=points)
    submit_child(client, credentials, chore)
    assert money(client, member) == 0
    [pending] = client.get("/api/approvals").json()
    assert pending["money_cents"] == 50
    updated = {k: chore[k] for k in ("room_id", "title", "icon", "interval_days")}
    updated.update(money_cents=100, child_xp=9)
    assert (
        client.put(f"/api/chores/{chore['id']}", json=updated, headers=csrf(parent)).status_code
        == 200
    )
    approve = f"/api/chore-approvals/{pending['id']}"
    headers = csrf(parent)
    with ThreadPoolExecutor(max_workers=3) as pool:
        codes = list(
            pool.map(lambda _: client.post(approve, headers=headers).status_code, range(3))
        )
    assert codes == [204] * 3
    assert money(client, member) == 50
    result = activity(client, member)
    [receipt] = result["transactions"]
    assert result["total"] == points and receipt["money_cents"] == 50
    week_url = f"/api/members/{member}/weekly-bonus?date={SATURDAY}"
    assert client.get(week_url).json()["earned_bonus_cents"] == 50
    undo_url = f"{approve}/confirmed"
    assert client.delete(undo_url, headers=headers).status_code == 204
    assert client.delete(undo_url, headers=headers).status_code == 204
    assert money(client, member) == 0
    assert client.get(week_url).json()["earned_bonus_cents"] == 0
    [inactive] = activity(client, member)["transactions"]
    assert inactive["inactive"] and inactive["money_cents"] == 50
    with ThreadPoolExecutor(max_workers=3) as pool:
        codes = list(
            pool.map(lambda _: restore_row(client, parent, inactive).status_code, range(3))
        )
    assert codes == [204] * 3
    assert money(client, member) == 50
    assert client.get(week_url).json()["earned_bonus_cents"] == 50
    with SessionLocal() as db:
        assert list(
            db.scalars(
                select(MoneyTransaction.amount_cents)
                .where(MoneyTransaction.kind.in_(("chore_completed", "chore_undone")))
                .order_by(MoneyTransaction.id)
            )
        ) == [50, -50, 50]


def test_rejection_creates_no_bonus_and_repeated_executions_are_independent(client, parent, now):
    member, credentials = add_person(client, parent, "Lena", "purple")
    chore = paid_chore(client, parent, member, repeatable=True, child_xp=0)
    submit_child(client, credentials, chore)
    [pending] = client.get("/api/approvals").json()
    assert (
        client.delete(f"/api/chore-approvals/{pending['id']}", headers=csrf(parent)).status_code
        == 204
    )
    assert money(client, member) == 0
    for key in ("b" * 32, "c" * 32):
        submit_child(client, credentials, chore, key)
        [pending] = client.get("/api/approvals").json()
        assert (
            client.post(f"/api/chore-approvals/{pending['id']}", headers=csrf(parent)).status_code
            == 204
        )
    assert money(client, member) == 100
    rows = activity(client, member)["transactions"]
    assert len(rows) == 2 and len({r["undo_id"] for r in rows}) == 2
    client.delete(f"/api/chore-approvals/{rows[0]['undo_id']}/confirmed", headers=csrf(parent))
    assert money(client, member) == 50


def test_parent_records_child_bonus_once_and_adult_gets_none(client, parent, lena, now):
    chore = paid_chore(client, parent, lena, child_xp=2, adult_xp=5, repeatable=True)
    assert done(client, parent, chore["id"], lena).status_code == 200
    assert done(client, parent, chore["id"], lena).status_code == 200
    assert money(client, lena) == 50
    adult = parent_member(client, parent, "Flo")
    assert (
        client.put(
            f"/api/chores/{chore['id']}/done",
            json={"member_id": adult, "request_key": "d" * 32},
            headers=csrf(parent),
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        assert (
            list(db.scalars(select(MoneyTransaction).where(MoneyTransaction.member_id == adult)))
            == []
        )
    # An attributed paid execution cannot silently move to another member.
    assert done(client, parent, chore["id"], adult).status_code == 409
    assert money(client, lena) == 50


def test_assigning_initially_unattributed_chore_credits_bonus_once(client, parent, lena, now):
    chore = paid_chore(client, parent, lena)
    assert done(client, parent, chore["id"]).status_code == 200
    assert money(client, lena) == 0
    assert done(client, parent, chore["id"], lena).status_code == 200
    assert done(client, parent, chore["id"], lena).status_code == 200
    assert money(client, lena) == 50
    assert client.delete(f"/api/chores/{chore['id']}/done", headers=csrf(parent)).status_code == 200
    assert money(client, lena) == 0


def test_task_and_chore_id_namespaces_do_not_mix_weekly_bonus(client, parent, lena, now):
    task = add_task(client, parent, [lena], points=0, money_cents=125)
    complete(client, parent, task, lena)
    chore = paid_chore(client, parent, lena)
    done(client, parent, chore["id"], lena)
    assert money(client, lena) == 175
    url = f"/api/members/{lena}/weekly-bonus?date={SATURDAY}"
    assert client.get(url).json()["earned_bonus_cents"] == 175
    rows = activity(client, lena)["transactions"]
    assert len(rows) == 2
    receipt = next(r for r in rows if r["undo_source"] == "chore")
    client.delete(f"/api/chore-approvals/{receipt['undo_id']}/confirmed", headers=csrf(parent))
    assert money(client, lena) == 125
    assert client.get(url).json()["earned_bonus_cents"] == 125


def test_paid_history_is_protected_and_legacy_edits_preserve_bonus(client, parent, lena, now):
    chore = paid_chore(client, parent, lena)
    body = {k: chore[k] for k in ("room_id", "title", "icon", "interval_days")}
    edited = client.put(f"/api/chores/{chore['id']}", json=body, headers=csrf(parent))
    assert edited.status_code == 200 and edited.json()["money_cents"] == 50
    done(client, parent, chore["id"], lena)
    assert client.delete(f"/api/chores/{chore['id']}", headers=csrf(parent)).status_code == 409
    assert (
        client.delete(f"/api/chores/rooms/{chore['room_id']}", headers=csrf(parent)).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/chores/{chore['id']}",
            json={**body, "counted_from": "2026-10-01"},
            headers=csrf(parent),
        ).status_code
        == 409
    )
    assert money(client, lena) == 50
    assert (
        client.put(
            f"/api/chores/{chore['id']}", json={**body, "money_cents": -1}, headers=csrf(parent)
        ).status_code
        == 422
    )


def test_enabling_bonus_does_not_retroactively_pay_existing_completion(client, parent, lena, now):
    chore = add_chore(
        client, parent, add_room(client, parent)["id"], child_enabled=True, child_member_ids=[lena]
    )
    done(client, parent, chore["id"], lena)
    body = {k: chore[k] for k in ("room_id", "title", "icon", "interval_days")}
    client.put(f"/api/chores/{chore['id']}", json={**body, "money_cents": 50}, headers=csrf(parent))
    done(client, parent, chore["id"], lena)
    assert money(client, lena) == 0


def test_mcp_cannot_change_approve_or_reverse_household_money(
    client, parent, lena, now, monkeypatch
):
    monkeypatch.setattr(get_settings(), "mcp_service_token", "s" * 40)
    with SessionLocal() as db:
        owner = db.scalar(select(User.id).where(User.role == "admin"))
    headers = {**service_headers(owner), "X-MCP-Parent-Confirmed": "true"}
    chore = paid_chore(client, parent, lena)
    body = {k: chore[k] for k in ("room_id", "title", "icon", "interval_days")}
    assert (
        client.post("/api/chores", json={**body, "money_cents": 50}, headers=headers).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/chores/{chore['id']}", json={**body, "money_cents": 0}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/chores/{chore['id']}/done", json={"member_id": lena}, headers=headers
        ).status_code
        == 403
    )
    assert done(client, parent, chore["id"], lena).status_code == 200
    [receipt] = activity(client, lena)["transactions"]
    assert (
        client.delete(
            f"/api/chore-approvals/{receipt['undo_id']}/confirmed", headers=headers
        ).status_code
        == 403
    )
    assert money(client, lena) == 50
    spec = client.get("/api/internal/mcp/schema", headers=headers).json()
    for name in ("ChoreIn", "ChoreCreateIn"):
        assert "money_cents" not in spec["components"]["schemas"][name]["properties"]


def test_household_correction_does_not_rewrite_closed_week(client, parent, lena, now):
    chore = paid_chore(client, parent, lena)
    done(client, parent, chore["id"], lena)
    response = client.post(
        f"/api/members/{lena}/weekly-bonus/close",
        json={"date": SATURDAY, "confirmed": True, "expected_total_cents": 50},
        headers=csrf(parent),
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_cents"] == 50
    assert client.delete(f"/api/chores/{chore['id']}/done", headers=csrf(parent)).status_code == 200
    state = client.get(f"/api/members/{lena}/criticism").json()
    assert state["requires_review"] is True and state["total_cents"] == 50
    assert money(client, lena) == 0
