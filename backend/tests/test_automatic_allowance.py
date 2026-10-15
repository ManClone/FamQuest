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


def test_weekly_credits_continue_and_are_distinct_from_bank_receipts(client, parent, lena, now):
    import datetime as dt

    from sqlalchemy.orm import Session

    from app.db import engine
    from app.models import BankTransaction, MemberBankAccount, MoneyPaymentMatch
    from app.money import allowance_balance, credit_configured_allowances

    client.put(
        f"/api/members/{lena}/money/settings",
        json={"weekly_amount_cents": 500},
        headers=csrf(parent),
    )
    with Session(engine) as db:
        assert credit_configured_allowances(db, dt.date(2026, 10, 10)) == [lena]
        assert credit_configured_allowances(db, dt.date(2026, 10, 10)) == []
        account = MemberBankAccount(member_id=lena, provider="test", display_name="Testkonto")
        db.add(account)
        db.flush()
        receipt = BankTransaction(
            account_id=account.id,
            external_id="receipt-1",
            booked_on=dt.date(2026, 9, 28),
            amount_cents=300,
        )
        db.add(receipt)
        db.flush()
        db.add(
            MoneyPaymentMatch(
                member_id=lena,
                bank_transaction_id=receipt.id,
                category="allowance",
                week_start=dt.date(2026, 9, 28),
                amount_cents=300,
            )
        )
        db.commit()
        assert allowance_balance(db, lena) == 1000
    status = client.get(f"/api/members/{lena}/money/allowance-payment-status").json()
    assert status["expected_cents"] == 500
    assert status["received_cents"] == 300
    assert status["missing_cents"] == 200
    assert status["bank_connected"] is True
