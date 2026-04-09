"""Add roadmap_features table and extend roadmap with item_type, feature, status, sort_order

Revision ID: e5f6a7b8c9d0
Revises: 733adcb9c3f1
Create Date: 2026-04-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = '733adcb9c3f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create roadmap_features table
    op.create_table(
        'roadmap_features',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # 2. Seed default features
    now = datetime.now(timezone.utc).isoformat()
    op.execute(f"""
        INSERT INTO roadmap_features (name, created_at) VALUES
        ('Marketing Audit', '{now}'),
        ('Accessibility Audit', '{now}'),
        ('Podcast Notes', '{now}'),
        ('Cold Outreach', '{now}'),
        ('Strategy Room', '{now}'),
        ('Admin UI', '{now}'),
        ('Platform Infrastructure', '{now}'),
        ('Etsy Shop', '{now}'),
        ('Gig Generator', '{now}')
    """)

    # 3. Add new columns to roadmap
    op.add_column('roadmap', sa.Column('item_type', sa.String(length=50), nullable=True))
    op.add_column('roadmap', sa.Column('feature_id', sa.BigInteger(), nullable=True))
    op.add_column('roadmap', sa.Column('sort_order', sa.Integer(), nullable=True))
    op.add_column('roadmap', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))

    # 4. Set defaults for new columns on existing rows
    op.execute("UPDATE roadmap SET item_type = 'New feature', sort_order = 0")

    # 5. Migrate old status enum values to new string values
    op.execute("UPDATE roadmap SET status = 'not_started' WHERE status = 'backlog'")
    op.execute("UPDATE roadmap SET status = 'done' WHERE status = 'completed'")
    # 'in_progress' stays as-is

    # 6. Change status column from enum to varchar
    op.execute("ALTER TABLE roadmap ALTER COLUMN status TYPE VARCHAR(50) USING status::text")
    op.execute("DROP TYPE IF EXISTS roadmap_status_enum")

    # 7. Add FK constraint for feature_id
    op.create_foreign_key(
        'fk_roadmap_feature_id',
        'roadmap', 'roadmap_features',
        ['feature_id'], ['id'],
        ondelete='SET NULL',
    )

    # 8. Seed test items
    op.execute(f"""
        INSERT INTO roadmap (title, description, item_type, feature_id, status, sort_order, created_at)
        SELECT
            'Roadmap tab in Strategy Room',
            'Add a Roadmap tab to the Strategy Room with Product Backlog and WIP sections, drag-and-drop priority ordering, and Recently Done functionality.',
            'New feature',
            (SELECT id FROM roadmap_features WHERE name = 'Strategy Room'),
            'in_progress',
            0,
            '{now}'
    """)
    op.execute(f"""
        INSERT INTO roadmap (title, description, item_type, feature_id, status, sort_order, created_at)
        SELECT
            'Reddit marketing agent',
            'Automated Reddit marketing agent to discover and engage with potential customers on relevant subreddits.',
            'New feature',
            (SELECT id FROM roadmap_features WHERE name = 'Cold Outreach'),
            'not_started',
            1,
            '{now}'
    """)


def downgrade() -> None:
    op.drop_constraint('fk_roadmap_feature_id', 'roadmap', type_='foreignkey')
    op.drop_column('roadmap', 'completed_at')
    op.drop_column('roadmap', 'sort_order')
    op.drop_column('roadmap', 'feature_id')
    op.drop_column('roadmap', 'item_type')

    # Restore status enum
    op.execute("""
        CREATE TYPE roadmap_status_enum AS ENUM ('backlog', 'in_progress', 'completed')
    """)
    op.execute("UPDATE roadmap SET status = 'backlog' WHERE status = 'not_started'")
    op.execute("UPDATE roadmap SET status = 'completed' WHERE status = 'done'")
    op.execute("""
        ALTER TABLE roadmap
        ALTER COLUMN status TYPE roadmap_status_enum
        USING status::roadmap_status_enum
    """)

    op.drop_table('roadmap_features')
