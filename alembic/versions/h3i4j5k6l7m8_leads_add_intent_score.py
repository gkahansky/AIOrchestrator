"""leads: add intent_score column (0-100 numeric intent signal from Claude)

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'h3i4j5k6l7m8'
down_revision = 'g2h3i4j5k6l7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('intent_score', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'intent_score')
