"""Phase 07 — NicReview + FinalReview tables.

Adds:
  * nic_reviews — per-application record of the reviewer's NIC decision
    (APPROVE / REJECT / OVERRIDE), with the selected 5-digit codes and a
    justification string. One row per decision; a single application can
    accumulate multiple rows if the reviewer re-decides after a re-classify.
  * final_reviews — signoff before portal submission (KYC confirmed,
    signoff method, remarks). Latest row is authoritative.

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-08-31 19:05:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID


# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nic_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "selected_codes",
            JSON,
            nullable=False,
            server_default="[]",
            comment="5-digit NIC codes the reviewer chose.",
        ),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column(
            "decision",
            sa.String(length=20),
            nullable=False,
            comment="APPROVE | REJECT | OVERRIDE",
        ),
        sa.Column(
            "decided_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_nic_reviews_application_id",
        "nic_reviews",
        ["application_id"],
    )
    op.create_check_constraint(
        "nic_reviews_decision_check",
        "nic_reviews",
        "decision in ('APPROVE','REJECT','OVERRIDE')",
    )

    op.create_table(
        "final_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "kyc_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "signoff_method",
            sa.String(length=50),
            nullable=False,
            comment="DIGITAL_SIGNATURE | AADHAAR_OTP",
        ),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "declared_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_final_reviews_application_id",
        "final_reviews",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_final_reviews_application_id", table_name="final_reviews")
    op.drop_table("final_reviews")
    op.drop_constraint("nic_reviews_decision_check", "nic_reviews", type_="check")
    op.drop_index("ix_nic_reviews_application_id", table_name="nic_reviews")
    op.drop_table("nic_reviews")