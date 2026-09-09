"""Phase 08 — Trigger-Action System tables.

Adds three tables that make state-transition reactions data-driven:

  * ``triggers`` — one row per rule. ``event_pattern`` is either a literal
    event name (``DOCUMENT_UPLOADED``) or a dot-segmented glob
    (``STATE_TRANSITIONED.*.NIC_REVIEW``). ``condition_json`` is an
    optional key/values dict matched against the event payload.
    Branch-scoped so a tenant can't trigger another tenant's actions.

  * ``actions`` — one row per execution step inside a trigger. ``type``
    selects the runner (HTTP_WEBHOOK / EMAIL / SHELL / STATE_TRANSITION /
    PLAYWRIGHT). ``config_json`` carries type-specific config. The CHECK
    constraint on ``type`` is the single source of truth for the
    supported action vocabulary.

  * ``email_outbox`` — durable audit trail of emails that EMAIL actions
    queued. Phase 12 will wire real SMTP/SendGrid delivery; for now the
    rows are how operators see "yes, the system noticed NIC_REVIEW".

Revision ID: f9e8a7b6c5d4
Revises: e7f8a9b0c1d2
Create Date: 2026-09-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID


revision = "f9e8a7b6c5d4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- triggers ---------------------------------------------------------
    op.create_table(
        "triggers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("event_pattern", sa.String(length=255), nullable=False),
        sa.Column(
            "condition_json",
            JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "last_run_json",
            JSON,
            nullable=True,
            comment="Last dispatch outcome: {at, matched, executed, error}.",
        ),
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
    # Dispatcher queries "active triggers for branch X" every event —
    # compound index on (branch_id, is_active) keeps that O(log n).
    op.create_index(
        "ix_triggers_branch_active",
        "triggers",
        ["branch_id", "is_active"],
    )

    # -- actions ----------------------------------------------------------
    op.create_table(
        "actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trigger_id",
            UUID(as_uuid=True),
            sa.ForeignKey("triggers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column(
            "config_json",
            JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_actions_trigger_id",
        "actions",
        ["trigger_id"],
    )
    op.create_check_constraint(
        "actions_type_check",
        "actions",
        "type in ('HTTP_WEBHOOK','EMAIL','SHELL','STATE_TRANSITION','PLAYWRIGHT')",
    )

    # -- email_outbox -----------------------------------------------------
    op.create_table(
        "email_outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("to_address", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "related_application_id",
            UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_trigger_id",
            UUID(as_uuid=True),
            sa.ForeignKey("triggers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_email_outbox_status",
        "email_outbox",
        ["status"],
    )
    op.create_check_constraint(
        "email_outbox_status_check",
        "email_outbox",
        "status in ('queued','sent','failed')",
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_status", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_constraint("actions_type_check", "actions", type_="check")
    op.drop_index("ix_actions_trigger_id", table_name="actions")
    op.drop_table("actions")
    op.drop_index("ix_triggers_branch_active", table_name="triggers")
    op.drop_table("triggers")