from tests.conftest import csrf


def test_configuring_amount_credits_current_week_once(client, parent, lena, now):
    url = f"/api/members/{lena}/money/settings"
    for _ in range(2):
        response = client.put(url, json={"weekly_amount_cents": 500}, headers=csrf(parent))
        assert response.status_code == 200, response.text
    assert client.get(f"/api/members/{lena}/money").json()["allowance_cents"] == 500
    status = client.get(f"/api/members/{lena}/money/allowance-payment-status").json()
    assert status == {
        "member_id": lena,
        "week_start": "2026-09-28",
        "expected_cents": 500,
        "received_cents": 0,
        "missing_cents": 500,
        "bank_connected": False,
    }
    assert (
        client.put(url, json={"weekly_amount_cents": 600}, headers=csrf(parent)).status_code == 200
    )
    assert client.get(f"/api/members/{lena}/money").json()["allowance_cents"] == 500
    assert (
        client.put(url, json={"weekly_amount_cents": None}, headers=csrf(parent)).status_code == 200
    )
    assert client.get(f"/api/members/{lena}/money").json()["allowance_cents"] == 500


def test_payment_status_requires_login(client, parent, lena):
    client.cookies.clear()
    assert client.get(f"/api/members/{lena}/money/allowance-payment-status").status_code == 401
