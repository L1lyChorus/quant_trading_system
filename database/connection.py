"""Database engine, session management, and schema initialization."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
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
        logger.info("Database initialized")

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session


def initialize_database(database_url: str = settings.database_url) -> Database:
    """Create and initialize a database without mixing in business logic."""
    database = Database(database_url)
    database.initialize()
    return database
