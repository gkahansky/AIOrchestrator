"""add market_research table

Revision ID: d1e2f3a4b5c6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = 'd1e2f3a4b5c6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'market_research',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('topic', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('selected_llms', JSONB(), nullable=False, server_default='[]'),
        sa.Column('critic_llm', sa.String(50), nullable=False, server_default='grok'),
        sa.Column('rag_doc_ids', JSONB(), nullable=True),
        sa.Column('optimized_prompts', JSONB(), nullable=True),
        sa.Column('research_results', JSONB(), nullable=True),
        sa.Column('merged_report', sa.Text(), nullable=True),
        sa.Column('critic_feedback', sa.Text(), nullable=True),
        sa.Column('final_report', sa.Text(), nullable=True),
        sa.Column('pdf_path', sa.String(2048), nullable=True),
        sa.Column('drive_link', sa.String(2048), nullable=True),
        sa.Column('client_email', sa.String(255), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_market_research_status', 'market_research', ['status'])


def downgrade() -> None:
    op.drop_index('ix_market_research_status', table_name='market_research')
    op.drop_table('market_research')
