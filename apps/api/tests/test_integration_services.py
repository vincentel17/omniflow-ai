import os

import psycopg
import pytest
from redis import Redis


@pytest.mark.integration
def test_database_connectivity() -> None:
    database_url = os.environ.get("DATABASE_URL", "postgresql://omniflow:omniflow@localhost:5432/omniflow")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            value = cur.fetchone()
    assert value == (1,)


@pytest.mark.integration
def test_redis_connectivity() -> None:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = Redis.from_url(redis_url)
    assert client.ping() is True
