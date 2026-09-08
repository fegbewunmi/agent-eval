"""Test DB fixture: uses the same Postgres instance as dev (docs/tech-stack.md - no
separate DB engine for tests), against a dedicated `agent_eval_test` database that is
schema-created fresh and dropped-clean per test via a transaction rollback.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register all models on Base.metadata

TEST_DATABASE_URL = os.environ.get(
    "AGENT_EVAL_TEST_DATABASE_URL",
    f"postgresql+psycopg://{os.environ.get('USER', 'postgres')}@localhost/agent_eval_test",
)


@pytest.fixture(scope="session")
def engine():
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    db_name = TEST_DATABASE_URL.rsplit("/", 1)[1]
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    eng = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, expire_on_commit=False)
    session = Session()

    original_commit = session.commit
    session.commit = session.flush  # keep everything inside the outer rollback-able transaction

    yield session

    session.commit = original_commit
    session.close()
    transaction.rollback()
    connection.close()
