"""API tests: preview is parent-only and must not book points."""

from tests.conftest import csrf


def test_weekly_preview_is_parent_only(client, admin, parent, lena):
    payload = {
        "member_id": lena,
        "date": "2026-10-14",
        "earned_bonus_points": 40,
        "penalty_points": 5,
    }
    assert client.post("/api/weekly-consequences/preview", json=payload, headers=csrf(admin)).status_code == 403
    response = client.post("/api/weekly-consequences/preview", json=payload, headers=csrf(parent))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "member_id": lena,
        "week_start": "2026-10-12",
        "week_end": "2026-10-18",
        "earned_bonus_points": 40,
        "penalty_points": 5,
        "payable_bonus_points": 35,
    }


def test_weekly_preview_rejects_negative_values(client, parent, lena):
    response = client.post(
        "/api/weekly-consequences/preview",
        json={"member_id": lena, "date": "2026-10-14", "earned_bonus_points": 10, "penalty_points": -1},
        headers=csrf(parent),
    )
    assert response.status_code == 422
