"""Shared test setup.

By default tests use a throwaway SQLite file: fast, no server needed.
Set TEST_DATABASE_URL to run the SAME tests against PostgreSQL (CI does both).
SQLite and Postgres differ in real ways (NUMERIC rounding, COPY, type coercion),
and a test suite that only ever sees SQLite can't catch those.

WARNING: tests drop and recreate every table in TEST_DATABASE_URL. Never point it
at a database you care about.
"""
import os

import pytest
from sqlalchemy import create_engine


@pytest.fixture(scope="module")
def make_engine(tmp_path_factory):
    engines = []

    def _make():
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            url = f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"
        engine = create_engine(url)
        engines.append(engine)
        return engine

    yield _make
    for e in engines:
        e.dispose()
