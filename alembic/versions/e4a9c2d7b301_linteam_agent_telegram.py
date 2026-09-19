"""add LINTEAM Agent Telegram identity and idempotency records

Revision ID: e4a9c2d7b301
Revises: c1d4e8f9a201
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4a9c2d7b301"
down_revision: str | None = "c1d4e8f9a201"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "communication_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("external_user_id", sa.String(200), nullable=False),
        sa.Column("external_chat_id", sa.String(200), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "external_user_id"),
    )
    for column in ("organization_id", "user_id", "channel"):
        op.create_index(
            f"ix_communication_identities_{column}", "communication_identities", [column]
        )
    op.create_table(
        "communication_link_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    for column in ("organization_id", "user_id", "channel", "expires_at"):
        op.create_index(
            f"ix_communication_link_tokens_{column}", "communication_link_tokens", [column]
        )
    op.create_table(
        "processed_channel_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("external_event_id", sa.String(200), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "external_event_id"),
    )
    op.create_index("ix_processed_channel_events_channel", "processed_channel_events", ["channel"])
    op.create_index(
        "ix_processed_channel_events_organization_id",
        "processed_channel_events",
        ["organization_id"],
    )
    op.create_table(
        "agent_confirmations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("external_confirmation_id", sa.String(120), nullable=False),
        sa.Column("intent", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "external_confirmation_id"),
    )
    for column in ("organization_id", "user_id", "channel"):
        op.create_index(f"ix_agent_confirmations_{column}", "agent_confirmations", [column])
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("external_user_id", sa.String(200), nullable=False),
        sa.Column("pending_intent", sa.String(80), nullable=False),
        sa.Column("step", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "external_user_id"),
    )
    for column in ("organization_id", "user_id", "channel", "expires_at"):
        op.create_index(f"ix_agent_sessions_{column}", "agent_sessions", [column])


def downgrade() -> None:
    for column in ("organization_id", "user_id", "channel", "expires_at"):
        op.drop_index(f"ix_agent_sessions_{column}", table_name="agent_sessions")
    op.drop_table("agent_sessions")
    for column in ("organization_id", "user_id", "channel"):
        op.drop_index(f"ix_agent_confirmations_{column}", table_name="agent_confirmations")
    op.drop_table("agent_confirmations")
    op.drop_index(
        "ix_processed_channel_events_organization_id", table_name="processed_channel_events"
    )
    op.drop_index("ix_processed_channel_events_channel", table_name="processed_channel_events")
    op.drop_table("processed_channel_events")
    for column in ("organization_id", "user_id", "channel", "expires_at"):
        op.drop_index(
            f"ix_communication_link_tokens_{column}", table_name="communication_link_tokens"
        )
    op.drop_table("communication_link_tokens")
    for column in ("organization_id", "user_id", "channel"):
        op.drop_index(
            f"ix_communication_identities_{column}", table_name="communication_identities"
        )
    op.drop_table("communication_identities")
