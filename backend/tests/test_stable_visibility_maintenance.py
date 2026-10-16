import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.cli import main
from app.db import SessionLocal
from app.models import PointTransaction, Praise
from tests.test_personal_access import add_person
from tests.test_points import book_manually, history
from tests.test_rewards import add_reward, redeem


def test_shared_rewards_keep_spending_and_other_personal_data_private(client, parent):
    one, credentials = add_person(client, parent, "Tim", "blue")
    two, other_credentials = add_person(client, parent, "Tom", "green")
    own_reward = add_reward(client, parent, one)
    other_reward = add_reward(client, parent, two)
    for member in (one, two):
        book_manually(client, parent, member, 10)
    # Parents may review both, but cannot spend a child's stars.
    assert redeem(client, parent, own_reward).status_code == 403
    with TestClient(client.app) as other:
        me = other.post("/api/auth/login", json=other_credentials).json()
        assert redeem(other, me, other_reward).status_code == 201
    with TestClient(client.app) as child:
        me = child.post("/api/auth/login", json=credentials).json()
        assert {m["id"] for m in child.get("/api/rewards/members").json()} == {one, two}
        assert {r["id"] for r in child.get("/api/rewards").json()} == {own_reward, other_reward}
        assert (
            child.get(f"/api/redemptions?member_id={two}").json()["redemptions"][0]["member_id"]
            == two
        )
        assert child.get(f"/api/members/{two}/points").status_code == 403
        assert child.get(f"/api/members/{two}/progress").status_code == 403
        assert redeem(child, me, other_reward).status_code == 403
        assert redeem(child, me, own_reward).status_code == 201
    assert history(client, one)["total"] == history(client, two)["total"] == 5


def test_consistency_report_is_read_only_and_distinguishes_level_xp(client, parent, now, capsys):
    member, credentials = add_person(client, parent, "Tim", "blue")
    book_manually(client, parent, member, 10, "Real credit")
    book_manually(client, parent, member, -1, "Test deduction")
    book_manually(client, parent, member, 1, "Test compensation")
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(PointTransaction))
    response = client.get("/api/maintenance/consistency")
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["read_only"]
    assert {f["code"] for f in report["findings"]} >= {
        "possible_manual_compensation",
        "possible_test_booking",
    }
    assert report["members"][0]["spendable_stars"] == 10
    assert report["members"][0]["earned_level_xp"] == 0
    assert not any(f["severity"] == "error" for f in report["findings"])
    assert main(["consistency-report"]) == 0
    assert json.loads(capsys.readouterr().out)["read_only"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PointTransaction)) == before
    with TestClient(client.app) as child:
        child.post("/api/auth/login", json=credentials)
        assert child.get("/api/maintenance/consistency").status_code == 403


def test_revoked_test_praise_is_not_reported_as_active(client, parent, lena, now):
    with SessionLocal() as db:
        from app.today import utcnow

        db.add(Praise(member_id=lena, reason="test", source_key="retired", revoked_at=utcnow()))
        db.commit()
    report = client.get("/api/maintenance/consistency").json()
    assert not any(f["code"] == "possible_test_praise" for f in report["findings"])
