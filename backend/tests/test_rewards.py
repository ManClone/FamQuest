import pytest

from tests.conftest import csrf
from tests.test_points import book_manually, history, points_of
from tests.test_tasks import add_member


def reward_data(member_id, **overrides) -> dict:
    return {
        "member_id": member_id,
        "name": "Ein Eis",
        "icon": "fluent-emoji-flat:soft-ice-cream",
        "cost": 5,
        **overrides,
    }


def add_reward(client, me, member_id, **overrides) -> int:
    response = client.post(
        "/api/rewards", json=reward_data(member_id, **overrides), headers=csrf(me)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def redeem(client, me, reward_id):
    return client.post(f"/api/rewards/{reward_id}/redeem", headers=csrf(me))


def add_parent_member(client, me, name="Mama", color="blue") -> int:
    response = client.post(
        "/api/members", json={"name": name, "role": "parent", "color": color}, headers=csrf(me)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_update_list_and_delete(client, parent, lena):
    reward = add_reward(client, parent, lena, name="  Ein Eis ", description=" lecker ")

    response = client.put(
        f"/api/rewards/{reward}",
        json=reward_data(lena, cost=8, active=False),
        headers=csrf(parent),
    )
    assert response.status_code == 200, response.text

    assert client.get("/api/rewards").json() == [
        {
            "id": reward,
            "member_id": lena,
            "name": "Ein Eis",
            "icon": "fluent-emoji-flat:soft-ice-cream",
            "description": "",
            "cost": 8,
            "active": False,
        }
    ]

    assert client.delete(f"/api/rewards/{reward}", headers=csrf(parent)).status_code == 204
    assert client.get("/api/rewards").json() == []


def test_rewards_are_per_child(client, parent, lena):
    tom = add_member(client, parent, "Tom", "green")
    add_reward(client, parent, lena, cost=20)
    add_reward(client, parent, tom, cost=10)
    add_reward(client, parent, lena, cost=5)

    rewards = client.get("/api/rewards").json()

    assert [(r["member_id"], r["cost"]) for r in rewards] == [(lena, 5), (lena, 20), (tom, 10)]


def test_adults_have_their_own_rewards(client, parent):
    mama = add_parent_member(client, parent)

    response = client.post("/api/rewards", json=reward_data(mama), headers=csrf(parent))

    assert response.status_code == 201
    assert response.json()["member_id"] == mama
    # Adults without a linked account cannot spend another profile's stars.
    assert redeem(client, parent, response.json()["id"]).status_code == 403
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import FamilyMember, User

    with SessionLocal() as db:
        db.get(FamilyMember, mama).user_id = db.scalar(select(User.id).where(User.role == "admin"))
        db.commit()
    book_manually(client, parent, mama, 10)
    assert redeem(client, parent, response.json()["id"]).status_code == 201
    assert history(client, mama)["total"] == 5


@pytest.mark.parametrize(
    "overrides, field, code",
    [
        ({"cost": 0}, "cost", "validation.out_of_range"),
        ({"cost": 1001}, "cost", "validation.out_of_range"),
        ({"name": "  "}, "name", "validation.too_short"),
        ({"icon": "<svg>"}, "icon", "validation.invalid_format"),
    ],
)
def test_reward_validation(client, parent, lena, overrides, field, code):
    response = client.post(
        "/api/rewards", json=reward_data(lena, **overrides), headers=csrf(parent)
    )

    assert response.status_code == 422
    assert response.json()["fields"] == {field: code}


def test_managing_rewards_requires_parent_role(client, parent, lena):
    reward = add_reward(client, parent, lena)
    account = client.post(
        "/api/auth/accounts",
        json={
            "email": "child-rewards@example.org",
            "password": "test-password-456",
            "role": "child",
        },
        headers=csrf(parent),
    )
    assert account.status_code == 201, account.text
    assert client.post("/api/auth/logout", headers=csrf(parent)).status_code == 204
    login = client.post(
        "/api/auth/login",
        json={"email": "child-rewards@example.org", "password": "test-password-456"},
    )
    assert login.status_code == 200, login.text
    child = login.json()
    assert (
        client.post("/api/rewards", json=reward_data(lena), headers=csrf(child)).status_code == 403
    )
    assert client.delete(f"/api/rewards/{reward}", headers=csrf(child)).status_code == 403
    assert (
        client.post(
            "/api/redemptions/1/cancel", json={"reason": "No longer wanted"}, headers=csrf(child)
        ).status_code
        == 403
    )
    assert client.get("/api/redemptions").status_code == 403
    # An unlinked child cannot see or redeem another member's rewards.
    assert client.get("/api/rewards").json() == []
    assert redeem(client, child, reward).json() == {"code": "profile.own_only"}


def test_redeem_books_points_and_stores_redemption(client, parent, lena, now):
    book_manually(client, parent, lena, 12)
    reward = add_reward(client, parent, lena, name="Ein Eis", cost=5)

    response = redeem(client, parent, reward)

    assert response.status_code == 201, response.text
    redemption = response.json()
    assert redemption["status"] == "redeemed"
    assert (redemption["reward_name"], redemption["cost"]) == ("Ein Eis", 5)
    assert points_of(client, lena) == {"today": 0, "total": 7}
    transaction = history(client, lena)["transactions"][0]
    assert (transaction["kind"], transaction["amount"], transaction["reason"]) == (
        "reward_redeemed",
        -5,
        "Ein Eis",
    )
    assert transaction["icon"] == "fluent-emoji-flat:soft-ice-cream"


def test_redeem_with_too_few_points(client, parent, lena):
    book_manually(client, parent, lena, 4)
    reward = add_reward(client, parent, lena, cost=5)

    response = redeem(client, parent, reward)

    assert response.status_code == 409
    assert response.json() == {"code": "reward.insufficient_points"}
    assert history(client, lena)["total"] == 4
    assert client.get("/api/redemptions").json()["redemptions"] == []


def test_balance_never_goes_negative(client, parent, lena):
    book_manually(client, parent, lena, 7)
    reward = add_reward(client, parent, lena, cost=5)

    assert redeem(client, parent, reward).status_code == 201
    # Ein zweiter Tipp scheitert, statt den Stand ins Minus zu bringen.
    assert redeem(client, parent, reward).status_code == 409
    assert history(client, lena)["total"] == 2


def test_inactive_and_unknown_rewards_cannot_be_redeemed(client, parent, lena):
    book_manually(client, parent, lena, 50)
    reward = add_reward(client, parent, lena, active=False)

    assert redeem(client, parent, reward).json() == {"code": "reward.inactive"}
    assert redeem(client, parent, 999).json() == {"code": "reward.not_found"}


def test_history_survives_changes_to_reward(client, parent, lena):
    book_manually(client, parent, lena, 50)
    reward = add_reward(client, parent, lena, name="Kino", cost=40)
    redeem(client, parent, reward)

    client.delete(f"/api/rewards/{reward}", headers=csrf(parent))

    [redemption] = client.get("/api/redemptions").json()["redemptions"]
    assert (redemption["reward_id"], redemption["reward_name"], redemption["cost"]) == (
        None,
        "Kino",
        40,
    )
    assert history(client, lena)["transactions"][0]["reason"] == "Kino"


def test_redemptions_filtered_and_paged(client, parent, lena):
    tom = add_member(client, parent, "Tom", "green")
    book_manually(client, parent, lena, 100)
    book_manually(client, parent, tom, 100)
    for cost in (1, 2, 3):
        redeem(client, parent, add_reward(client, parent, lena, cost=cost))
    redeem(client, parent, add_reward(client, parent, tom, cost=4))

    everyone = client.get("/api/redemptions").json()["redemptions"]
    assert [r["cost"] for r in everyone] == [4, 3, 2, 1]

    first = client.get("/api/redemptions", params={"member_id": lena, "limit": 2}).json()
    assert [r["cost"] for r in first["redemptions"]] == [3, 2]
    assert first["has_more"] is True
    rest = client.get(
        "/api/redemptions",
        params={"member_id": lena, "before": first["redemptions"][-1]["id"]},
    ).json()
    assert [r["cost"] for r in rest["redemptions"]] == [1]
    assert rest["has_more"] is False


def test_cancel_redemption_refunds_original_cost_once_with_audit(client, parent, lena):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import PointTransaction

    book_manually(client, parent, lena, 12)
    reward = add_reward(client, parent, lena, cost=5)
    redemption = redeem(client, parent, reward).json()
    # Historical purchases remain refundable after changing or deleting the reward.
    client.put(f"/api/rewards/{reward}", json=reward_data(lena, cost=50), headers=csrf(parent))
    client.delete(f"/api/rewards/{reward}", headers=csrf(parent))
    path = f"/api/redemptions/{redemption['id']}/cancel"
    assert client.post(path, json={"reason": "   "}, headers=csrf(parent)).status_code == 422
    assert history(client, lena)["total"] == 7
    response = client.post(path, json={"reason": "  No longer wanted  "}, headers=csrf(parent))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "cancelled"
    assert result["cancellation_reason"] == "No longer wanted"
    assert result["cancelled_at"] is not None
    assert client.post(path, json={"reason": "Retry"}, headers=csrf(parent)).json() == result
    assert history(client, lena)["total"] == 12
    assert client.get("/api/redemptions").json()["redemptions"] == [result]
    with SessionLocal() as db:
        refunds = list(
            db.scalars(select(PointTransaction).where(PointTransaction.kind == "reward_cancelled"))
        )
        assert len(refunds) == 1
        assert refunds[0].amount == 5
        assert refunds[0].created_by_user_id is not None
    assert (
        client.post(
            "/api/redemptions/99999/cancel", json={"reason": "Missing"}, headers=csrf(parent)
        ).status_code
        == 404
    )


def test_simultaneous_cancellations_refund_only_once(client, parent, lena):
    from concurrent.futures import ThreadPoolExecutor

    book_manually(client, parent, lena, 10)
    reward = add_reward(client, parent, lena, cost=5)
    redemption = redeem(client, parent, reward).json()

    def cancel(_):
        return client.post(
            f"/api/redemptions/{redemption['id']}/cancel",
            json={"reason": "No longer wanted"},
            headers=csrf(parent),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(cancel, range(4)))
    assert [response.status_code for response in responses] == [200] * 4
    assert history(client, lena)["total"] == 10
    assert (
        len(
            [
                entry
                for entry in history(client, lena)["transactions"]
                if entry["kind"] == "reward_cancelled"
            ]
        )
        == 1
    )


def test_adults_can_edit_each_others_rewards_but_only_spend_their_own_points(client, parent):
    from fastapi.testclient import TestClient

    mama = add_parent_member(client, parent)
    credentials = {"email": "viola@example.org", "password": "test-password-123"}
    response = client.post(
        "/api/members",
        json={"name": "Viola", "role": "parent", "color": "purple", "login": credentials},
        headers=csrf(parent),
    )
    assert response.status_code == 201, response.text
    viola = response.json()["id"]
    reward = add_reward(client, parent, viola)
    own_reward = add_reward(client, parent, mama)
    book_manually(client, parent, viola, 10)
    assert redeem(client, parent, reward).status_code == 403
    assert history(client, viola)["total"] == 10
    assert client.get(f"/api/redemptions?member_id={viola}").status_code == 200
    with TestClient(client.app) as partner:
        me = partner.post("/api/auth/login", json=credentials).json()
        assert (
            partner.put(
                f"/api/rewards/{own_reward}",
                json=reward_data(mama, name="Edited by Viola"),
                headers=csrf(me),
            ).status_code
            == 200
        )
        assert redeem(partner, me, own_reward).status_code == 403
        assert redeem(partner, me, reward).status_code == 201
    assert (
        client.put(
            f"/api/rewards/{reward}",
            json=reward_data(viola, name="Edited by Flo"),
            headers=csrf(parent),
        ).status_code
        == 200
    )
    assert history(client, viola)["total"] == 5
