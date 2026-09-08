"""Database engine, session management, and schema initialization."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from database.models import Base

logger = logging.getLogger(__name__)


class Database:
    """Owns the SQLAlchemy engine and session factory."""

    def __init__(self, database_url: str = settings.database_url) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        self._migrate_sqlite_market_bars()
        logger.info("Database initialized")

    def _migrate_sqlite_market_bars(self) -> None:
        """Add market-data columns to existing SQLite databases without touching trading tables."""
        if self.engine.dialect.name != "sqlite":
            return
        inspector = inspect(self.engine)
        if "market_bars" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("market_bars")}
        if "bar_status" in columns:
            return
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE market_bars "
                    "ADD COLUMN bar_status VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN'"
                )
            )

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session


def initialize_database(database_url: str = settings.database_url) -> Database:
    """Create and initialize a database without mixing in business logic."""
    database = Database(database_url)
    database.initialize()
    return database
