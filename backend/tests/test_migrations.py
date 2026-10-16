import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.db import SessionLocal
from tests.conftest import alembic_config


def test_migrations_upgrade_and_downgrade():
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_models_match_migrations():
    # Schlägt fehl, wenn Modelle geändert wurden, ohne eine Migration anzulegen.
    command.check(alembic_config())


def test_adult_tasks_are_removed():
    """Aufgaben nur für Erwachsene verschwinden; gemischte verlieren nur deren Zuordnung."""
    config = alembic_config()
    command.downgrade(config, "8fc58f53970c")
    statements = [
        "INSERT INTO family_members (id, name, role, color) VALUES"
        " (1, 'Lena', 'child', 'purple'), (2, 'Mama', 'parent', 'blue'),"
        " (3, 'Papa', 'parent', 'orange')",
        "INSERT INTO tasks (id, title, icon, points) VALUES"
        " (1, 'Zähne', 'x', 1), (2, 'Bad putzen', 'x', 1), (3, 'Tisch', 'x', 1),"
        " (4, 'Verwaist', 'x', 1)",
        "INSERT INTO task_recurrences (task_id, kind) VALUES"
        " (1, 'daily'), (2, 'daily'), (3, 'daily'), (4, 'daily')",
        "INSERT INTO task_assignments (task_id, member_id) VALUES"
        " (1, 1), (2, 2), (2, 3), (3, 1), (3, 2)",
        "INSERT INTO task_completions (task_id, member_id, date) VALUES"
        " (1, 1, '2026-10-01'), (2, 2, '2026-10-01')",
        "INSERT INTO point_transactions (member_id, amount, kind, task_id, task_date) VALUES"
        " (2, 1, 'task_completed', 2, '2026-10-01')",
    ]
    with SessionLocal() as db:
        for statement in statements:
            db.execute(sa.text(statement))
        db.commit()

    command.upgrade(config, "head")

    def rows(query):
        with SessionLocal() as db:
            return [tuple(row) for row in db.execute(sa.text(query))]

    assert rows("SELECT id FROM tasks ORDER BY id") == [(1,), (3,), (4,)]
    assert rows("SELECT task_id, member_id FROM task_assignments ORDER BY task_id") == [
        (1, 1),
        (3, 1),
    ]
    assert rows("SELECT task_id, member_id FROM task_completions") == [(1, 1)]
    # Die Punktebuchung bleibt, nur ihr Verweis auf die Aufgabe ist leer.
    assert rows("SELECT member_id, amount, task_id FROM point_transactions") == [(2, 1, None)]


def test_migrations_have_single_head():
    """Verhindert versehentlich parallele Alembic-Migrationszweige."""
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()
    assert len(heads) == 1, f"Expected one migration head, got: {heads}"


def test_household_upgrade_preserves_completions_and_xp():
    config = alembic_config()
    command.downgrade(config, "d20261015repeat")
    with SessionLocal() as db:
        for statement in [
            "INSERT INTO family_members (id,name,role,color) VALUES (1,'Flo','parent','blue')",
            "INSERT INTO chore_rooms (id,name,icon) VALUES (1,'Kitchen','x')",
            "INSERT INTO chores (id,room_id,title,icon,interval_days,anchor_date) "
            "VALUES (1,1,'Cook','x',1,'2026-10-16')",
            "INSERT INTO chore_completions (id,chore_id,member_id,date) "
            "VALUES (1,1,1,'2026-10-16')",
            "INSERT INTO chore_credits (completion_id,member_id,amount) VALUES (1,1,7)",
        ]:
            db.execute(sa.text(statement))
        db.commit()
    command.upgrade(config, "head")
    with SessionLocal() as db:
        assert tuple(
            db.execute(
                sa.text("SELECT approved, request_key FROM chore_completions WHERE id=1")
            ).one()
        ) == (True, None)
        assert db.scalar(sa.text("SELECT amount FROM chore_credits WHERE completion_id=1")) == 7
        assert tuple(
            db.execute(
                sa.text("SELECT repeatable, child_enabled, child_member_ids FROM chores WHERE id=1")
            ).one()
        ) == (False, False, [])
