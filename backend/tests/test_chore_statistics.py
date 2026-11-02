import datetime as dt

from app.db import SessionLocal
from app.models import ChoreCompletion
from tests.test_adult_chore_credits import parent_member
from tests.test_chores import add_chore, add_room


def test_statistics_ranges_include_boundaries_but_not_pending_or_future(client, parent, now):
    adult = parent_member(client, parent, "Flo")
    chore = add_chore(client, parent, add_room(client, parent)["id"])
    with SessionLocal() as db:
        for day in ("2026-09-27", "2026-09-04", "2025-10-04", "2025-10-03", "2026-10-04"):
            db.add(
                ChoreCompletion(
                    chore_id=chore["id"],
                    member_id=adult,
                    date=dt.date.fromisoformat(day),
                    approved=True,
                    estimated_minutes=15,
                )
            )
        db.add(
            ChoreCompletion(
                chore_id=chore["id"],
                member_id=adult,
                date=dt.date(2026, 10, 2),
                approved=False,
                estimated_minutes=99,
            )
        )
        db.commit()
    for days, count in ((7, 1), (30, 2), (365, 3)):
        response = client.get("/api/chores", params={"share_days": days})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["share_days"] == days
        assert data["shares"] == [
            {"member_id": adult, "count": count, "estimated_minutes": 15 * count}
        ]
    assert client.get("/api/chores").json()["share_days"] == 30
    for invalid in (0, 14, 366):
        assert client.get("/api/chores", params={"share_days": invalid}).status_code == 422
