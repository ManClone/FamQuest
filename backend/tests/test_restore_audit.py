"""Migration comparison detects business losses without exposing private row data."""

from sqlalchemy import create_engine, text

from app.restore_audit import compare_databases, upload_manifest


def test_added_columns_and_removed_local_passwords_preserve_business_comparison(tmp_path):
    source = create_engine(f"sqlite:///{tmp_path / 'before.db'}")
    target = create_engine(f"sqlite:///{tmp_path / 'after.db'}")
    try:
        for engine in (source, target):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT, password_hash TEXT)"
                    )
                )
                connection.execute(
                    text("INSERT INTO users VALUES (1, 'parent', 'private-original-hash')")
                )
                connection.execute(
                    text("CREATE TABLE points(id INTEGER PRIMARY KEY, amount INTEGER)")
                )
                connection.execute(text("INSERT INTO points VALUES (1, 47)"))
        with target.begin() as connection:
            connection.execute(text("ALTER TABLE points ADD COLUMN new_snapshot INTEGER"))
            connection.execute(text("UPDATE users SET password_hash = '!'"))
        assert compare_databases(source, target) == {"tables_compared": 2, "differences": []}
        with target.begin() as connection:
            connection.execute(text("UPDATE points SET amount=46"))
        result = compare_databases(source, target)
        assert result["differences"] == [
            {
                "table": "points",
                "reason": "business_data_differ",
                "source_rows": 1,
                "target_rows": 1,
            }
        ]
        assert "private-original-hash" not in str(result)
        assert "47" not in str(result)
    finally:
        source.dispose()
        target.dispose()


def test_missing_business_rows_and_columns_are_not_ignored(tmp_path):
    source = create_engine(f"sqlite:///{tmp_path / 'before.db'}")
    target = create_engine(f"sqlite:///{tmp_path / 'after.db'}")
    try:
        with source.begin() as connection:
            connection.execute(text("CREATE TABLE quests(id INTEGER PRIMARY KEY, title TEXT)"))
            connection.execute(text("INSERT INTO quests VALUES (1, 'private child task')"))
        with target.begin() as connection:
            connection.execute(text("CREATE TABLE quests(id INTEGER PRIMARY KEY)"))
        assert compare_databases(source, target)["differences"] == [
            {"table": "quests", "reason": "missing_business_schema"}
        ]
    finally:
        source.dispose()
        target.dispose()


def test_upload_comparison_includes_relative_paths_and_contents(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    for root in (before, after):
        (root / "avatars").mkdir(parents=True)
        (root / "avatars" / "same.webp").write_bytes(b"family image")
    assert upload_manifest(before) == upload_manifest(after)
    (after / "avatars" / "same.webp").write_bytes(b"other family image")
    assert upload_manifest(before) != upload_manifest(after)
