"""Time uses per-execution estimates; counts stay compatible for child statistics."""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ChoreCompletion
from tests.conftest import SATURDAY, csrf
from tests.test_adult_chore_credits import parent_member
from tests.test_chores import add_chore, add_room, plan, update
from tests.test_personal_access import add_person


def test_snapshot_survives_edits_retries_attribution_and_individual_undo(client, parent, now):
    flo = parent_member(client, parent, "Flo")
    viola = parent_member(client, parent, "Viola", "orange")
    room = add_room(client, parent)
    chore = add_chore(client, parent, room["id"], repeatable=True, estimated_minutes=60)
    path = f"/api/chores/{chore['id']}/done"
    first = {"member_id": flo, "request_key": "a" * 32}
    assert client.put(path, json=first, headers=csrf(parent)).status_code == 200
    assert update(client, parent, chore, estimated_minutes=5).status_code == 200
    assert client.put(path, json=first, headers=csrf(parent)).status_code == 200
    assert plan(client)["shares"] == [{"member_id": flo, "count": 1, "estimated_minutes": 60}]
    # Later attribution transfers the original time, not today's five-minute estimate.
    assert (
        client.put(path, json=first | {"member_id": viola}, headers=csrf(parent)).status_code == 200
    )
    second = {"member_id": viola, "request_key": "b" * 32}
    completion = client.put(path, json=second, headers=csrf(parent)).json()
    assert plan(client)["shares"] == [{"member_id": viola, "count": 2, "estimated_minutes": 65}]
    result = client.delete(
        path, params={"completion_id": completion["last_completion_id"]}, headers=csrf(parent)
    )
    assert result.status_code == 200
    assert plan(client)["shares"] == [{"member_id": viola, "count": 1, "estimated_minutes": 60}]


def test_pending_child_execution_counts_only_after_approval_with_original_time(client, parent, now):
    child_id, credentials = add_person(client, parent, "Tim", "purple")
    room = add_room(client, parent)
    chore = add_chore(
        client,
        parent,
        room["id"],
        child_enabled=True,
        child_member_ids=[child_id],
        repeatable=True,
        estimated_minutes=12,
    )
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        assert (
            child.put(
                f"/api/chores/mine/{chore['id']}/done",
                json={"request_key": "c" * 32},
                headers=csrf(me),
            ).status_code
            == 200
        )
    assert plan(client)["shares"] == []
    assert update(client, parent, chore, estimated_minutes=99).status_code == 200
    approval = client.get("/api/approvals").json()[0]
    assert (
        client.post(f"/api/chore-approvals/{approval['id']}", headers=csrf(parent)).status_code
        == 204
    )
    assert plan(client)["shares"] == [{"member_id": child_id, "count": 1, "estimated_minutes": 12}]


def test_old_estimates_fallback_but_unapproved_unassigned_and_out_of_range_do_not_count(
    client, parent, now
):
    flo = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    chore = add_chore(client, parent, room["id"], repeatable=True, estimated_minutes=25)
    today = dt.date.fromisoformat(SATURDAY)
    with SessionLocal() as db:
        for index, (member_id, approved, date, minutes) in enumerate(
            [
                (flo, True, today, None),
                (flo, False, today, 90),
                (None, True, today, 80),
                (flo, True, today - dt.timedelta(days=30), 70),
                (flo, True, today + dt.timedelta(days=1), 60),
            ]
        ):
            db.add(
                ChoreCompletion(
                    chore_id=chore["id"],
                    member_id=member_id,
                    approved=approved,
                    date=date,
                    estimated_minutes=minutes,
                    request_key=str(index) * 32,
                )
            )
        db.commit()
    assert plan(client)["shares"] == [{"member_id": flo, "count": 1, "estimated_minutes": 25}]
    with SessionLocal() as db:
        # Reading the report must not rewrite the unknown historical estimate.
        assert (
            db.scalar(
                select(ChoreCompletion).where(ChoreCompletion.request_key == "0" * 32)
            ).estimated_minutes
            is None
        )
