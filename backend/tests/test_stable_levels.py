from sqlalchemy import select

from app.db import SessionLocal
from app.levels import required_praise, threshold, unlocked_level
from app.models import FamilyMember
from tests.conftest import csrf
from tests.test_today import add_task, complete, undo


def test_level_curve_and_praise_milestones():
    assert [threshold(i) for i in range(2, 11)] == [50, 110, 175, 245, 320, 400, 485, 575, 670]
    assert [required_praise(i) for i in range(2, 11)] == [0, 0, 1, 0, 0, 2, 0, 0, 3]
    assert unlocked_level(10000, 0) == 3
    assert unlocked_level(399, 2) == 6
    assert unlocked_level(400, 1) == 6
    assert unlocked_level(400, 2) == 7
    assert unlocked_level(174, 10) == 3
    assert unlocked_level(399, 0, previous=4) == 6
    assert unlocked_level(575, 0, previous=8) == 9


def test_praise_unlocks_saved_xp_and_corrections_keep_level(client, parent, lena, now):
    task = add_task(client, parent, [lena], points=485)
    assert complete(client, parent, task, lena).status_code == 204
    path = f"/api/members/{lena}/progress"
    data = client.get(path).json()
    assert data["level"] == 3 and data["remaining_xp"] == 0 and data["remaining_praise"] == 1
    praises = []
    for i, expected in [(1, 6), (2, 8)]:
        reply = client.post(
            f"/api/members/{lena}/praise",
            json={"reason": "Helpful", "request_key": f"{i:032x}"},
            headers=csrf(parent),
        )
        assert reply.status_code == 201, reply.text
        praises.append(reply.json()["id"])
        assert client.get(path).json()["level"] == expected
    # Preserve an earned level even when the child never opened their progress page.
    with SessionLocal() as db:
        assert db.scalar(select(FamilyMember.highest_level).where(FamilyMember.id == lena)) == 8
    assert undo(client, parent, task, lena).status_code == 204
    for praise_id in praises:
        assert (
            client.post(
                f"/api/members/{lena}/praise/{praise_id}/revoke",
                json={"reason": "Correction"},
                headers=csrf(parent),
            ).status_code
            == 200
        )
    after = client.get(path).json()
    assert after["level"] == 8 and after["earned_xp"] == 0 and after["praise_count"] == 0
    assert after["level_progress"] == 0 and after["remaining_xp"] == 575
