"""
backend/db.py
SQLite engine and session management via SQLModel.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "synapse.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    """Create all tables defined via SQLModel metadata."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """FastAPI dependency: yields a DB session."""
    with Session(engine) as session:
        yield session
