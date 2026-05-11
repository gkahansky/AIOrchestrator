"""roadmap: add owner column

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('roadmap', sa.Column('owner', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('roadmap', 'owner')
