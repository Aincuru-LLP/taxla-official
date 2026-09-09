"""Phase 12 — External Webhook tables.

Adds two tables that let branches subscribe to state-machine events:

  * ``webhooks`` — one row per subscribed URL. ``secret`` is the HMAC key
    minted at create-time. ``subscribed_events`` is a JSON list of
    ``fnmatch``-style patterns (empty list means "all events").
    Branch-scoped on FK to ``branches.id`` with CASCADE so deleting a
    branch also cleans up its subscriptions.

  * ``webhook_deliveries`` — append-only delivery log. One row per attempt
    with status code, response body, and any error. Cascade-deleted with
    its parent webhook so a subscription delete clears its log too.

Index strategy: deliveries are read most often as "last N attempts for
webhook X ordered by time" — a compound index on (webhook_id,
attempted_at DESC) covers that scan.

Revision ID: a1b2c3d4e5f6
Revises: f9e8a7b6c5d4
Create Date: 2026-09-01 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID


revision = "a1b2c3d4e5f6"
down_revision = "f9e8a7b6c5d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- webhooks ---------------------------------------------------------
    op.create_table(
        "webhooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret", sa.String(length=64), nullable=False),
        sa.Column(
            "subscribed_events",
            JSON,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "last_triggered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("last_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    # Dispatcher hot-path: "active webhooks for branch X". Same compound
    # pattern as triggers/actions.
    op.create_index(
        "ix_webhooks_branch_active",
        "webhooks",
        ["branch_id", "is_active"],
    )

    # -- webhook_deliveries ----------------------------------------------
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "webhook_id",
            UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_name", sa.String(length=255), nullable=True),
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column(
            "attempted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
    )
    # Delivery-log scan: "last 50 attempts for webhook X" — covered by
    # the compound (webhook_id, attempted_at) index.
    op.create_index(
        "ix_webhook_deliveries_webhook_time",
        "webhook_deliveries",
        ["webhook_id", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_webhook_time", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhooks_branch_active", table_name="webhooks")
    op.drop_table("webhooks")