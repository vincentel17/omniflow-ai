from __future__ import annotations

import uuid

from sqlalchemy import select

from .db import SessionLocal
from .models import Membership, Org, Role, User, VerticalPack
from .services.phase4 import ensure_pipeline_templates, ensure_sla_config
from .settings import settings


def main() -> None:
    dev_user_id = uuid.UUID(settings.dev_user_id)
    dev_org_id = uuid.UUID(settings.dev_org_id)
    with SessionLocal() as db:
        org = db.scalar(select(Org).where(Org.id == dev_org_id))
        if org is None:
            org = Org(id=dev_org_id, name="OmniFlow Dev Org")
            db.add(org)

        user = db.scalar(select(User).where(User.id == dev_user_id))
        if user is None:
            user = User(id=dev_user_id, email="dev@omniflow.local", full_name="Dev User")
            db.add(user)
        db.flush()

        membership = db.scalar(
            select(Membership).where(Membership.org_id == dev_org_id, Membership.user_id == dev_user_id)
        )
        if membership is None:
            db.add(Membership(org_id=dev_org_id, user_id=dev_user_id, role=Role.OWNER))

        vertical_pack = db.scalar(select(VerticalPack).where(VerticalPack.org_id == dev_org_id))
        if vertical_pack is None:
            vertical_pack = VerticalPack(org_id=dev_org_id, pack_slug="generic")
            db.add(vertical_pack)
            db.flush()

        ensure_pipeline_templates(db=db, org_id=dev_org_id, pack_slug=vertical_pack.pack_slug)
        ensure_sla_config(db=db, org_id=dev_org_id)

        db.commit()
    print(f"Seed complete: org={dev_org_id} user={dev_user_id} pack=generic")


if __name__ == "__main__":
    main()
