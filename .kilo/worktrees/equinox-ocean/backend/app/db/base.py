"""SQLAlchemy declarative base and JSON utility types."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class JSONType(TypeDecorator):
    """Stores arbitrary JSON as TEXT for SQLite compatibility."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value: Any | None, dialect: Any) -> Any:
        if value is None:
            return None
        return json.loads(value)
