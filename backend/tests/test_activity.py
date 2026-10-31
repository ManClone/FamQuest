"""Unified display/correction history must not duplicate or guess executions."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import PointTransaction
from tests.conftest import csrf
from tests.test_adult_chore_credits import parent_member
from tests.test_chores import add_chore, add_room, done
from tests.test_repeatable_tasks import execute
from tests.test_today import add_task, complete


def activity(client, member_id, **params):
    response = client.get(f"/api/members/{member_id}/activity", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_task_appears_once_and_correction_stays_in_same_history(client, parent, lena, now):
    task = add_task(client, parent, [lena], money_cents=50)
    assert complete(client, parent, task, lena).status_code == 204
    [row] = activity(client, lena)["transactions"]
    assert row["undo_source"] == "task"
    assert (
        client.delete(
            f"/api/approvals/{row['undo_id']}/confirmed", headers=csrf(parent)
        ).status_code
        == 204
    )
    result = activity(client, lena)
    assert result["total"] == 0
    assert [r["kind"] for r in result["transactions"]] == ["task_undone", "task_completed"]
    assert all(r["undo_id"] is None for r in result["transactions"])


def test_zero_points_euro_bonus_has_one_correctable_entry_and_preserves_refund(
    client, parent, lena, now
):
    task = add_task(client, parent, [lena], points=0, money_cents=50)
    assert complete(client, parent, task, lena).status_code == 204
    [row] = activity(client, lena)["transactions"]
    assert row["amount"] == 0
    assert row["money_cents"] == 50
    assert row["undo_source"] == "task"
    assert (
        client.delete(
            f"/api/approvals/{row['undo_id']}/confirmed", headers=csrf(parent)
        ).status_code
        == 204
    )
    rows = activity(client, lena)["transactions"]
    assert [r["money_cents"] for r in rows] == [-50, 50]
    assert all(r["undo_id"] is None for r in rows)


def test_equal_repeat_executions_have_distinct_exact_targets(client, parent, lena, now):
    task = add_task(client, parent, [lena], repeatable=True, points=2)
    for key in ("a" * 32, "b" * 32):
        assert execute(client, parent, task, lena, key).status_code == 204
        [pending] = client.get("/api/approvals").json()
        assert (
            client.post(f"/api/approvals/{pending['id']}", headers=csrf(parent)).status_code == 204
        )
    rows = activity(client, lena)["transactions"]
    assert len(rows) == 2
    assert len({r["undo_id"] for r in rows}) == 2
    selected = rows[1]["undo_id"]
    assert (
        client.delete(f"/api/approvals/{selected}/confirmed", headers=csrf(parent)).status_code
        == 204
    )
    remaining = [r for r in activity(client, lena)["transactions"] if r["undo_id"] is not None]
    assert len(remaining) == 1
    assert remaining[0]["undo_id"] == rows[0]["undo_id"]


def test_legacy_task_credit_has_safe_transaction_time_link(client, parent, lena, now):
    task = add_task(client, parent, [lena])
    complete(client, parent, task, lena)
    with SessionLocal() as db:
        entry = db.scalar(select(PointTransaction).where(PointTransaction.member_id == lena))
        entry.completion_source = None
        entry.completion_id = None
        db.commit()
    [row] = activity(client, lena)["transactions"]
    assert row["undo_source"] == "task"
    assert row["undo_id"] is not None


def test_chore_credit_and_zero_credit_are_both_single_entries(client, parent, now):
    adult = parent_member(client, parent, "Flo")
    room = add_room(client, parent)
    chore = add_chore(client, parent, room["id"], adult_xp=5)
    assert done(client, parent, chore["id"], adult).status_code == 200
    [row] = activity(client, adult)["transactions"]
    assert row["amount"] == 5
    assert row["undo_source"] == "chore"
    zero = add_chore(client, parent, room["id"], title="Zero", adult_xp=0)
    assert done(client, parent, zero["id"], adult).status_code == 200
    rows = activity(client, adult)["transactions"]
    assert len(rows) == 2
    assert len({r["id"] for r in rows}) == 2
    assert sorted(r["amount"] for r in rows) == [0, 5]


def test_activity_cursor_and_member_filter_cover_all_sources(client, parent, lena, now):
    task = add_task(client, parent, [lena], points=2)
    zero = add_task(client, parent, [lena], points=0, money_cents=50)
    blank = add_task(client, parent, [lena], points=0)
    for item in (task, zero, blank):
        complete(client, parent, item, lena)
    page = activity(client, lena, limit=1)
    ids = []
    while True:
        ids.extend(r["id"] for r in page["transactions"])
        if not page["has_more"]:
            break
        page = activity(client, lena, limit=1, cursor=page["next_cursor"])
    assert len(ids) == len(set(ids)) == 3
    assert client.get(f"/api/members/{lena}/activity?cursor=bad").status_code == 422
