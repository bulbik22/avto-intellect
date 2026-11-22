"""Store the verifier for each session's rotating refresh token."""

import sqlalchemy as sa
from alembic import op


revision = "0002_session_refresh"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sessions", sa.Column("refresh_digest", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("sessions", "refresh_digest")
