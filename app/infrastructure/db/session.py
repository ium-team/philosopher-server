from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.infrastructure.db.base import Base

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


def init_db() -> None:
    # Ensure model metadata is registered before create_all.
    from app.infrastructure.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_projects_schema()


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
