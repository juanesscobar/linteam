"""allow existing members to assign work

Revision ID: d2f4a7b9c1e3
Revises: e8c1d7f3a9b2
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2f4a7b9c1e3"
down_revision: str | None = "e8c1d7f3a9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

memberships = sa.table(
    "memberships",
    sa.column("id", sa.Uuid()),
    sa.column("permissions", sa.JSON()),
)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.select(memberships.c.id, memberships.c.permissions)).all()
    for membership_id, permissions in rows:
        values = list(permissions or [])
        if "workitem.assign" not in values and "*" not in values:
            bind.execute(
                memberships.update()
                .where(memberships.c.id == membership_id)
                .values(permissions=[*values, "workitem.assign"])
            )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.select(memberships.c.id, memberships.c.permissions)).all()
    for membership_id, permissions in rows:
        values = [value for value in (permissions or []) if value != "workitem.assign"]
        bind.execute(
            memberships.update()
            .where(memberships.c.id == membership_id)
            .values(permissions=values)
        )
