import os

from celery import Celery

broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("omniflow-worker", broker=broker_url, backend=broker_url)


@app.task(name="worker.health.ping")
def ping() -> str:
    return "pong"
