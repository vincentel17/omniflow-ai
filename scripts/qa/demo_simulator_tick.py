from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_ROOT = REPO_ROOT / "apps" / "worker"
API_ROOT = REPO_ROOT / "apps" / "api"
for path in (str(API_ROOT), str(WORKER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omniflow_worker.main import demo_simulator_tick  # noqa: E402


def main() -> None:
    processed = demo_simulator_tick()
    print(f"Demo simulator tick processed: {processed}")


if __name__ == "__main__":
    main()
