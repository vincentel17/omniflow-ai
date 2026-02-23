from __future__ import annotations

import uuid

from sqlalchemy import Select, select

from app.models import Event
from app.tenancy import org_scoped


def test_org_scoped_helper_filters_by_org_id() -> None:
    org_id = uuid.uuid4()
    stmt: Select[tuple[Event]] = select(Event)
    scoped_stmt = org_scoped(stmt, org_id, Event)
    compiled = str(scoped_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert str(org_id).replace("-", "") in compiled
    assert "events.org_id" in compiled
