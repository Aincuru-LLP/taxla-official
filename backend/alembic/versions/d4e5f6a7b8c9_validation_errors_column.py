"""Add validation_errors JSON column to extracted_data.

Phase 04 — the validation engine now records per-field format errors
(detailed list of which validators failed and why). Previously the
``validation_status`` column carried only PASS / FAIL / UNVERIFIED.

Revision ID: d4e5f6a7b8c9
Revises: c0a1b2d3e4f5
Create Date: 2026-08-31 16:55:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c0a1b2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the validation_errors JSON column to extracted_data."""
    op.add_column(
        "extracted_data",
        sa.Column(
            "validation_errors",
            JSON,
            nullable=True,
            comment=(
                "Per-field format-error list. Each entry is "
                "{validator: str, message: str}. Null when no errors."
            ),
        ),
    )


def downgrade() -> None:
    """Drop the validation_errors column."""
    op.drop_column("extracted_data", "validation_errors")