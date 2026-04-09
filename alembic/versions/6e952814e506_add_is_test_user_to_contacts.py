"""add is_test_user to contacts

Revision ID: 6e952814e506
Revises: c1d2e3f4a5b6
Create Date: 2026-04-08 21:20:32.986622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e952814e506'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('contacts', sa.Column('is_test_user', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contacts', 'is_test_user')
