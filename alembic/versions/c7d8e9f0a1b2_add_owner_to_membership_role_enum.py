"""add owner to membership role enum

Revision ID: c7d8e9f0a1b2
Revises: b75a45911c77
Create Date: 2025-11-24 00:06:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = 'b75a45911c77'
branch_labels = None
depends_on = None


def upgrade():
    # Add OWNER value to membership_role enum
    op.execute("ALTER TYPE membership_role ADD VALUE IF NOT EXISTS 'OWNER'")


def downgrade():
    # Note: PostgreSQL doesn't support removing enum values easily
    # This would require recreating the enum type
    pass