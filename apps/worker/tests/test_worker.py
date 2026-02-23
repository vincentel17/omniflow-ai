from omniflow_worker.main import ping


def test_ping_task() -> None:
    assert ping() == "pong"
