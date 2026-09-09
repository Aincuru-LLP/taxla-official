"""OCR confidence separation + raw_ocr_results table

Phase 02 follow-up: separate OCR/extraction/final confidence, add processing-
version columns to extracted_data, and persist raw OCR artifacts in their own
table so extraction can be re-run without re-OCR.

Revision ID: c0a1b2d3e4f5
Revises: 8c51d318289f
Create Date: 2026-08-31 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0a1b2d3e4f5'
down_revision: Union[str, Sequence[str], None] = '8c51d318289f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. New table: raw_ocr_results (durable OCR artifact per page)
    op.create_table(
        'raw_ocr_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('line_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_confidence', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('ocr_engine', sa.String(length=50), nullable=False),
        sa.Column('ocr_engine_version', sa.String(length=50), nullable=True),
        sa.Column('preprocessing_version', sa.String(length=50), nullable=True),
        sa.Column('processing_version', sa.String(length=50), nullable=True),
        sa.Column('bounding_boxes', sa.JSON(), nullable=True),
        sa.Column('language_packs', sa.JSON(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_raw_ocr_results_document_id', 'raw_ocr_results', ['document_id'])

    # 2. extracted_data: separate confidence signals + processing provenance
    op.add_column('extracted_data', sa.Column('ocr_confidence', sa.Numeric(precision=4, scale=3), nullable=True))
    op.add_column('extracted_data', sa.Column('extraction_confidence', sa.Numeric(precision=4, scale=3), nullable=True))
    op.add_column('extracted_data', sa.Column('final_confidence', sa.Numeric(precision=4, scale=3), nullable=True))
    op.add_column('extracted_data', sa.Column('review_decision', sa.String(length=50), nullable=True))
    op.add_column('extracted_data', sa.Column('extraction_model', sa.String(length=100), nullable=True))
    op.add_column('extracted_data', sa.Column('extraction_prompt_version', sa.String(length=50), nullable=True))
    op.add_column('extracted_data', sa.Column('schema_version', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('extracted_data', 'schema_version')
    op.drop_column('extracted_data', 'extraction_prompt_version')
    op.drop_column('extracted_data', 'extraction_model')
    op.drop_column('extracted_data', 'review_decision')
    op.drop_column('extracted_data', 'final_confidence')
    op.drop_column('extracted_data', 'extraction_confidence')
    op.drop_column('extracted_data', 'ocr_confidence')
    op.drop_index('ix_raw_ocr_results_document_id', table_name='raw_ocr_results')
    op.drop_table('raw_ocr_results')