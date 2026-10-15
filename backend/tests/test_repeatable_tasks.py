import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import MoneyTransaction, TaskCompletion
from tests.conftest import csrf
from tests.test_today import add_task, complete, completion_url, today, undo


def execute(client, parent, task, member, key):
    return client.put(completion_url(task, member) + f"&request_key={key}", headers=csrf(parent))


def test_each_execution_is_approved_and_rewarded_once(client, parent, lena, now):
    task = add_task(client, parent, [lena], repeatable=True, points=3, money_cents=50)
    first = "a" * 32
    second = "b" * 32
    assert execute(client, parent, task, lena, first).status_code == 204
    assert execute(client, parent, task, lena, first).status_code == 204
    pending = client.get("/api/approvals").json()
    assert len(pending) == 1
    assert today(client)["tasks"][0]["pending_member_ids"] == [lena]
    assert (
        client.post(f"/api/approvals/{pending[0]['id']}", headers=csrf(parent)).status_code == 204
    )
    assert today(client)["tasks"][0]["done_member_ids"] == []
    assert execute(client, parent, task, lena, first).status_code == 204
    assert client.get("/api/approvals").json() == []
    assert execute(client, parent, task, lena, second).status_code == 204
    pending = client.get("/api/approvals").json()
    assert len(pending) == 1
    assert (
        client.post(f"/api/approvals/{pending[0]['id']}", headers=csrf(parent)).status_code == 204
    )
    assert today(client)["points"][0]["total"] == 6
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(TaskCompletion)) == 2
        assert db.scalar(select(func.sum(MoneyTransaction.amount_cents))) == 100
    assert undo(client, parent, task, lena).status_code == 204
    assert today(client)["points"][0]["total"] == 6


def test_only_one_execution_can_wait_for_approval(client, parent, lena, now):
    task = add_task(client, parent, [lena], repeatable=True)
    assert execute(client, parent, task, lena, "a" * 32).status_code == 204
    assert execute(client, parent, task, lena, "b" * 32).status_code == 204
    assert len(client.get("/api/approvals").json()) == 1
    assert undo(client, parent, task, lena).status_code == 204
    assert client.get("/api/approvals").json() == []
    assert execute(client, parent, task, lena, "c" * 32).status_code == 204


def test_normal_tasks_remain_once_per_day(client, parent, lena, now):
    task = add_task(client, parent, [lena])
    for _ in range(2):
        assert complete(client, parent, task, lena).status_code == 204
    assert today(client)["points"][0]["total"] == 2
    assert execute(client, parent, task, lena, "a" * 32).status_code == 422


@pytest.mark.parametrize("key", [None, "bad"])
def test_repeat_execution_requires_valid_key(client, parent, lena, now, key):
    task = add_task(client, parent, [lena], repeatable=True)
    response = (
        complete(client, parent, task, lena)
        if key is None
        else execute(client, parent, task, lena, key)
    )
    assert response.status_code == 422
    assert client.get("/api/approvals").json() == []


def test_rejected_execution_can_be_repeated(client, parent, lena, now):
    task = add_task(client, parent, [lena], repeatable=True)
    assert execute(client, parent, task, lena, "a" * 32).status_code == 204
    entry = client.get("/api/approvals").json()[0]
    assert client.delete(f"/api/approvals/{entry['id']}", headers=csrf(parent)).status_code == 204
    assert execute(client, parent, task, lena, "b" * 32).status_code == 204
    assert len(client.get("/api/approvals").json()) == 1
