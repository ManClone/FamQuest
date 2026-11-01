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
    [inactive] = result["transactions"]
    assert inactive["inactive"] is True
    assert inactive["restore_id"] is not None
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
    [inactive] = rows
    assert inactive["money_cents"] == 50
    assert inactive["inactive"] is True
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


def restore_row(client, parent, row):
    return client.post(
        f"/api/activity-corrections/{row['restore_id']}/restore",
        json={"confirmed": True},
        headers=csrf(parent),
    )


def test_restore_frozen_task_then_undo_again_preserves_one_receipt(client, parent, lena, now):
    from app.models import MoneyTransaction
    from tests.test_tasks import task_data

    task = add_task(client, parent, [lena], points=2, money_cents=50)
    complete(client, parent, task, lena)
    [row] = activity(client, lena)["transactions"]
    undo_url = f"/api/approvals/{row['undo_id']}/confirmed"
    assert client.delete(undo_url, headers=csrf(parent)).status_code == 204
    [inactive] = activity(client, lena)["transactions"]
    assert inactive["inactive"]
    assert (
        client.put(
            f"/api/tasks/{task}",
            json=task_data([lena], points=9, money_cents=100),
            headers=csrf(parent),
        ).status_code
        == 200
    )
    for _ in range(2):
        response = restore_row(client, parent, inactive)
        assert response.status_code == 204, response.text
    result = activity(client, lena)
    [active] = result["transactions"]
    assert active["id"] == inactive["id"]
    assert active["reactivated"] and not active["inactive"]
    assert result["total"] == 2
    assert client.get(f"/api/members/{lena}/money").json()["bonus_cents"] == 50
    assert client.delete(undo_url, headers=csrf(parent)).status_code == 204
    [again] = activity(client, lena)["transactions"]
    assert again["inactive"] and again["id"] == active["id"]
    assert activity(client, lena)["total"] == 0
    with SessionLocal() as db:
        assert list(db.scalars(select(PointTransaction.amount).order_by(PointTransaction.id))) == [
            2,
            -2,
            2,
            -2,
        ]
        assert list(
            db.scalars(select(MoneyTransaction.amount_cents).order_by(MoneyTransaction.id))
        ) == [50, -50, 50, -50]


def test_parallel_restores_credit_original_only_once(client, parent, lena, now):
    from concurrent.futures import ThreadPoolExecutor

    task = add_task(client, parent, [lena], points=3, money_cents=50)
    complete(client, parent, task, lena)
    [row] = activity(client, lena)["transactions"]
    client.delete(f"/api/approvals/{row['undo_id']}/confirmed", headers=csrf(parent))
    [inactive] = activity(client, lena)["transactions"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(
            pool.map(lambda _: restore_row(client, parent, inactive).status_code, range(4))
        )
    assert codes == [204] * 4
    result = activity(client, lena)
    assert result["total"] == 3 and len(result["transactions"]) == 1
    assert client.get(f"/api/members/{lena}/money").json()["bonus_cents"] == 50


def test_recompletion_blocks_restore_without_double_credit(client, parent, lena, now):
    task = add_task(client, parent, [lena], points=2)
    complete(client, parent, task, lena)
    [row] = activity(client, lena)["transactions"]
    client.delete(f"/api/approvals/{row['undo_id']}/confirmed", headers=csrf(parent))
    [inactive] = activity(client, lena)["transactions"]
    complete(client, parent, task, lena)
    assert restore_row(client, parent, inactive).status_code == 409
    result = activity(client, lena)
    assert result["total"] == 2
    assert len(result["transactions"]) == 2
    assert sum(bool(r.get("inactive")) for r in result["transactions"]) == 1


def test_zero_point_bonus_restore_and_explicit_confirmation(client, parent, lena, now):
    task = add_task(client, parent, [lena], points=0, money_cents=50)
    complete(client, parent, task, lena)
    [row] = activity(client, lena)["transactions"]
    client.delete(f"/api/approvals/{row['undo_id']}/confirmed", headers=csrf(parent))
    [inactive] = activity(client, lena)["transactions"]
    url = f"/api/activity-corrections/{inactive['restore_id']}/restore"
    assert client.post(url, json={"confirmed": False}, headers=csrf(parent)).status_code == 422
    assert restore_row(client, parent, inactive).status_code == 204
    [active] = activity(client, lena)["transactions"]
    assert not active["inactive"] and active["amount"] == 0 and active["money_cents"] == 50
    assert client.get(f"/api/members/{lena}/money").json()["bonus_cents"] == 50


def test_chore_direct_undo_and_restore_keep_original_credit(client, parent, now):
    adult = parent_member(client, parent, "Flo")
    chore = add_chore(client, parent, add_room(client, parent)["id"], adult_xp=5)
    done(client, parent, chore["id"], adult)
    assert client.delete(f"/api/chores/{chore['id']}/done", headers=csrf(parent)).status_code == 200
    [inactive] = activity(client, adult)["transactions"]
    assert inactive["inactive"]
    assert restore_row(client, parent, inactive).status_code == 204
    assert activity(client, adult)["total"] == 5
    assert client.delete(f"/api/chores/{chore['id']}/done", headers=csrf(parent)).status_code == 200
    [again] = activity(client, adult)["transactions"]
    assert again["inactive"] and again["id"] == inactive["id"]
    assert activity(client, adult)["total"] == 0


def test_manual_credit_can_be_reversed_restored_and_reversed_again(client, parent, lena):
    response = client.post(
        f"/api/members/{lena}/points", json={"amount": 4, "reason": "Extra"}, headers=csrf(parent)
    )
    assert response.status_code in (200, 201), response.text
    [row] = activity(client, lena)["transactions"]
    reverse_url = f"/api/members/{lena}/points/{row['id']}/reverse"
    assert (
        client.post(reverse_url, json={"reason": "Mistake"}, headers=csrf(parent)).status_code
        == 200
    )
    [inactive] = activity(client, lena)["transactions"]
    assert inactive["inactive"] and activity(client, lena)["total"] == 0
    assert restore_row(client, parent, inactive).status_code == 204
    # Retrying an old reversal must not undo a later restoration.
    assert (
        client.post(reverse_url, json={"reason": "Mistake"}, headers=csrf(parent)).status_code
        == 200
    )
    assert activity(client, lena)["total"] == 4
    assert (
        client.post(
            f"/api/activity-corrections/{inactive['correction_id']}/deactivate",
            json={"confirmed": True, "reason": "Again"},
            headers=csrf(parent),
        ).status_code
        == 204
    )
    [again] = activity(client, lena)["transactions"]
    assert again["inactive"] and activity(client, lena)["total"] == 0


def test_repeatable_restore_preserves_other_executions(client, parent, lena, now):
    task = add_task(client, parent, [lena], repeatable=True, points=2)
    for key in ("a" * 32, "b" * 32):
        execute(client, parent, task, lena, key)
        [pending] = client.get("/api/approvals").json()
        assert (
            client.post(f"/api/approvals/{pending['id']}", headers=csrf(parent)).status_code == 204
        )
    rows = activity(client, lena)["transactions"]
    selected = rows[0]
    client.delete(f"/api/approvals/{selected['undo_id']}/confirmed", headers=csrf(parent))
    inactive = next(r for r in activity(client, lena)["transactions"] if r.get("inactive"))
    assert restore_row(client, parent, inactive).status_code == 204
    result = activity(client, lena)
    assert result["total"] == 4 and len(result["transactions"]) == 2
    assert len({r["undo_id"] for r in result["transactions"]}) == 2


def test_today_undo_zero_credit_is_retained_and_missing_task_cannot_restore(
    client, parent, lena, now
):
    from tests.test_today import undo

    task = add_task(client, parent, [lena], points=0)
    complete(client, parent, task, lena)
    assert undo(client, parent, task, lena).status_code == 204
    [inactive] = activity(client, lena)["transactions"]
    assert inactive["inactive"] and inactive["amount"] == 0
    assert client.delete(f"/api/tasks/{task}", headers=csrf(parent)).status_code == 204
    assert restore_row(client, parent, inactive).status_code == 409
    assert activity(client, lena)["transactions"][0]["inactive"]


def test_restore_requires_parent_account(client, parent, lena, now):
    task = add_task(client, parent, [lena])
    complete(client, parent, task, lena)
    [row] = activity(client, lena)["transactions"]
    client.delete(f"/api/approvals/{row['undo_id']}/confirmed", headers=csrf(parent))
    [inactive] = activity(client, lena)["transactions"]
    account = client.post(
        "/api/auth/accounts",
        json={
            "email": "restore-child@example.org",
            "password": "test-password-456",
            "role": "child",
        },
        headers=csrf(parent),
    )
    assert account.status_code == 201
    client.post("/api/auth/logout", headers=csrf(parent))
    login = client.post(
        "/api/auth/login",
        json={"email": "restore-child@example.org", "password": "test-password-456"},
    )
    assert login.status_code == 200
    assert restore_row(client, login.json(), inactive).status_code == 403
