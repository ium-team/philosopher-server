from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import Conversation, Philosopher

settings = get_settings()
DATABASE_URL = settings.database_url or "sqlite:///./.local/philosopher.db"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _ensure_projects_schema() -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "projects" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("projects")}

        if "instruction" not in columns:
            connection.execute(text("ALTER TABLE projects ADD COLUMN instruction TEXT"))

        if "is_default" not in columns:
            if connection.dialect.name == "postgresql":
                connection.execute(
                    text("ALTER TABLE projects ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE"),
                )
            else:
                connection.execute(text("ALTER TABLE projects ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT 0"))

        if "is_pinned" not in columns:
            if connection.dialect.name == "postgresql":
                connection.execute(
                    text("ALTER TABLE projects ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT FALSE"),
                )
            else:
                connection.execute(text("ALTER TABLE projects ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0"))

        refreshed_indexes = {index["name"] for index in inspect(connection).get_indexes("projects")}
        if "ix_projects_is_default" not in refreshed_indexes:
            connection.execute(text("CREATE INDEX ix_projects_is_default ON projects (is_default)"))
        if "ix_projects_is_pinned" not in refreshed_indexes:
            connection.execute(text("CREATE INDEX ix_projects_is_pinned ON projects (is_pinned)"))


def _quote_ident(value: str) -> str:
    return value.replace('"', '""')


def _quote_literal(value: str) -> str:
    return value.replace("'", "''")


def _ensure_philosopher_enum_schema() -> None:
    with engine.begin() as connection:
        if connection.dialect.name != "postgresql":
            return

        enum_type_name = Conversation.__table__.c.philosopher.type.name or "philosopher"
        rows = connection.execute(
            text(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = :enum_type_name
                ORDER BY e.enumsortorder
                """,
            ),
            {"enum_type_name": enum_type_name},
        ).all()
        existing_values = {str(row[0]) for row in rows}

        if not existing_values:
            return

        escaped_type = _quote_ident(enum_type_name)
        for philosopher in Philosopher:
            if philosopher.value in existing_values:
                continue
            escaped_value = _quote_literal(philosopher.value)
            connection.execute(
                text(
                    f"ALTER TYPE \"{escaped_type}\" ADD VALUE IF NOT EXISTS '{escaped_value}'",
                ),
            )


def init_db() -> None:
    # Ensure model metadata is registered before create_all.
    from app.infrastructure.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_projects_schema()
    _ensure_philosopher_enum_schema()


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
