"""Automatic schema reconciliation for SQLite and PostgreSQL.

Ensures all tables and newly added model columns are present in the database.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine, inspect, text

from app.db.base import Base

logger = logging.getLogger(__name__)


def sync_schema(engine: Engine) -> None:
    """Compare Base.metadata against the connected database and add any missing columns/tables."""
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        with engine.begin() as conn:
            for table_name, table in Base.metadata.tables.items():
                if table_name not in existing_tables:
                    table.create(conn)
                    existing_tables.add(table_name)
                    logger.info("Created missing table: %s", table_name)
                    continue

                existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                for column in table.columns:
                    if column.name not in existing_cols:
                        col_type = column.type.compile(engine.dialect)
                        default_clause = ""
                        if column.default is not None and hasattr(
                            column.default, "arg"
                        ):
                            arg: Any = column.default.arg
                            if callable(arg):
                                default_clause = ""
                            elif isinstance(arg, (int, float)):
                                default_clause = f" DEFAULT {arg}"
                            elif isinstance(arg, str):
                                default_clause = f" DEFAULT '{arg}'"
                        elif not column.nullable:
                            # SQLite requires DEFAULT when adding NOT NULL column to non-empty table
                            default_clause = " DEFAULT ''"

                        stmt = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{default_clause}"
                        conn.execute(text(stmt))
                        logger.info(
                            "Added missing column %s.%s via: %s",
                            table_name,
                            column.name,
                            stmt,
                        )
    except Exception:
        logger.exception("schema synchronization encountered an error")
        raise
