"""organization codes and secure member invites

Revision ID: e8c1d7f3a9b2
Revises: fbb8a7715582
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8c1d7f3a9b2"
down_revision: str | None = "fbb8a7715582"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(length=30), nullable=True))
    op.execute("UPDATE organizations SET code = 'LINTEAM' WHERE code IS NULL")
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.alter_column("code", nullable=False)
        batch_op.create_unique_constraint("uq_organizations_code", ["code"])
    op.create_table(
        "organization_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_organization_invites_organization_id", "organization_invites", ["organization_id"])
    op.create_index("ix_organization_invites_email", "organization_invites", ["email"])
    op.create_index("ix_organization_invites_expires_at", "organization_invites", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_organization_invites_expires_at", table_name="organization_invites")
    op.drop_index("ix_organization_invites_email", table_name="organization_invites")
    op.drop_index("ix_organization_invites_organization_id", table_name="organization_invites")
    op.drop_table("organization_invites")
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_constraint("uq_organizations_code", type_="unique")
        batch_op.drop_column("code")
