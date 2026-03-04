from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import inspect

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import engine  # noqa: E402


def _quote_ident(name: str) -> str:
    return f'"{name.replace("\"", "\"\"")}"'


def main() -> None:
    if os.getenv("ALLOW_QA_RESET", "").lower() not in {"1", "true", "yes"}:
        raise SystemExit("Refusing to reset demo DB. Set ALLOW_QA_RESET=true.")

    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "production":
        raise SystemExit("Refusing to reset demo DB in production APP_ENV.")

    inspector = inspect(engine)
    tables = [table for table in inspector.get_table_names(schema="public") if table != "alembic_version"]
    if not tables:
        print("Reset complete: no data tables found.")
        return

    qualified = ", ".join(f'public.{_quote_ident(name)}' for name in tables)
    with engine.begin() as conn:
        conn.exec_driver_sql(f"TRUNCATE TABLE {qualified} RESTART IDENTITY CASCADE;")

    print(f"Reset complete: truncated {len(tables)} tables.")


if __name__ == "__main__":
    main()
