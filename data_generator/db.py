"""PostgreSQL access: connections, bulk load with COPY, row counts.

Connection settings come from environment variables. `make` loads them from
.env (through `uv run --env-file .env`), so nothing is hard-coded here.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import psycopg
from psycopg import sql

from data_generator.records import column_names, row_values

SOURCE_DATABASES = ("ecommerce", "crm", "erp")


def connect(dbname: str) -> psycopg.Connection:
    """Connection as the `generator` role (owner of the source databases).

    Used as a context manager, the connection commits on success and rolls
    back on error: each database is loaded all-or-nothing.
    """
    password = os.environ.get("GENERATOR_PASSWORD")
    if not password:
        raise RuntimeError(
            "GENERATOR_PASSWORD is not set. Run through make (which loads .env), "
            "or export the variable."
        )
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=dbname,
        user="generator",
        password=password,
        application_name="data_generator",
    )


def truncate(conn: psycopg.Connection, tables: Sequence[str]) -> None:
    """Empty tables and restart their identity sequences."""
    query = sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
        sql.SQL(", ").join(sql.Identifier(t) for t in tables)
    )
    conn.execute(query)


def copy_records(conn: psycopg.Connection, table: str, records: Sequence[object]) -> int:
    """Bulk load records with COPY: one streamed command instead of one INSERT per row."""
    if not records:
        return 0
    columns = column_names(type(records[0]))
    query = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(sql.Identifier(c) for c in columns)
    )
    with conn.cursor() as cur, cur.copy(query) as copy:
        for record in records:
            copy.write_row(row_values(record))
    return len(records)


def sync_identity(conn: psycopg.Connection, table: str, column: str) -> None:
    """Move the identity sequence past the loaded ids.

    COPY writes explicit ids, so the sequence does not advance by itself; without
    this, the next INSERT would try id 1 and fail with a duplicate key error.
    """
    query = sql.SQL(
        "SELECT setval(pg_get_serial_sequence({table_name}, {column_name}), "
        "COALESCE(MAX({column}), 0) + 1, false) FROM {table}"
    ).format(
        table_name=sql.Literal(table),
        column_name=sql.Literal(column),
        column=sql.Identifier(column),
        table=sql.Identifier(table),
    )
    conn.execute(query)


def table_counts(dbname: str) -> list[tuple[str, int]]:
    """Exact row count of every table in the public schema."""
    with connect(dbname) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
        ]
        counts = []
        for table in tables:
            query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            counts.append((table, conn.execute(query).fetchone()[0]))
        return counts
