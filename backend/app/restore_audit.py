"""Read-only comparison of a restored source family and its migrated test copy.

Credentials and transient sessions are deliberately excluded. Their correct
central relocation is checked separately by identity-copy tests and preflight.
No rows, secrets or connection strings are printed.
"""

import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import MetaData, create_engine, select

TRANSIENT_TABLES = {"alembic_version", "sessions", "mcp_actions"}


def business_columns(table):
    return [
        column.name
        for column in table.columns
        if not any(part in column.name.lower() for part in ("password", "token", "secret"))
        and not column.name.lower().startswith("pin_")
        and not column.name.lower().endswith("_pin")
    ]


def table_digest(connection, table, columns):
    rows = [
        json.dumps(list(row), ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":"))
        for row in connection.execute(select(*(table.c[name] for name in columns)))
    ]
    digest = hashlib.sha256()
    for row in sorted(rows):
        digest.update(row.encode("utf-8") + b"\n")
    return {"rows": len(rows), "sha256": digest.hexdigest()}


def compare_databases(source, target):
    differences = []
    compared = 0
    with source.connect() as original, target.connect() as restored:
        for connection in (original, restored):
            if connection.dialect.name == "postgresql":
                connection.execution_options(isolation_level="REPEATABLE READ")
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        before, after = MetaData(), MetaData()
        before.reflect(bind=original)
        after.reflect(bind=restored)
        for name, table in sorted(before.tables.items()):
            if name in TRANSIENT_TABLES:
                continue
            columns = business_columns(table)
            if name not in after.tables or not set(columns) <= set(after.tables[name].c.keys()):
                differences.append({"table": name, "reason": "missing_business_schema"})
                continue
            a = table_digest(original, table, columns)
            b = table_digest(restored, after.tables[name], columns)
            compared += 1
            if a != b:
                differences.append(
                    {
                        "table": name,
                        "reason": "business_data_differ",
                        "source_rows": a["rows"],
                        "target_rows": b["rows"],
                    }
                )
    return {"tables_compared": compared, "differences": differences}


def upload_manifest(directory):
    root = Path(directory).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Upload root must be a directory")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Upload comparison refuses symbolic links")
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("Upload path escapes the selected directory")
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result[path.relative_to(root).as_posix()] = (resolved.stat().st_size, digest.hexdigest())
    return result


def main():
    # URLs stay out of process arguments and output. Both directories must be
    # explicit; a DB-only comparison never masquerades as a complete restore check.
    source = create_engine(os.environ["SOURCE_DATABASE_URL"])
    target = create_engine(os.environ["TARGET_DATABASE_URL"])
    try:
        result = compare_databases(source, target)
        original = upload_manifest(os.environ["SOURCE_UPLOAD_DIR"])
        restored = upload_manifest(os.environ["TARGET_UPLOAD_DIR"])
        result["upload_files_compared"] = len(original)
        result["uploads_equal"] = original == restored
        print(json.dumps(result, sort_keys=True))
        if result["differences"] or not result["uploads_equal"]:
            raise SystemExit(1)
    finally:
        target.dispose()
        source.dispose()


if __name__ == "__main__":
    main()
