"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-09

"""
from alembic import op

from app.database.base import Base
from app.database import models  # noqa: F401  -- registers all tables on Base.metadata

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
