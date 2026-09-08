"""add revocable API tokens for external agents

Revision ID: c1d4e8f9a201
Revises: ab026585cbe0
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d4e8f9a201"
down_revision: str | None = "d2f4a7b9c1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "agent_api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_prefix"),
    )
    op.create_index(
        op.f("ix_agent_api_tokens_organization_id"), "agent_api_tokens", ["organization_id"]
    )
    op.create_index(op.f("ix_agent_api_tokens_agent_id"), "agent_api_tokens", ["agent_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_api_tokens_agent_id"), table_name="agent_api_tokens")
    op.drop_index(op.f("ix_agent_api_tokens_organization_id"), table_name="agent_api_tokens")
    op.drop_table("agent_api_tokens")
