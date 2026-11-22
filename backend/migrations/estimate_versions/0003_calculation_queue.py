"""Track durable calculation requests and worker results."""

from alembic import op
import sqlalchemy as sa


revision = "0003_calculation_queue"
down_revision = "0002_photos"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assessments", sa.Column("submitted_version", sa.Integer()))
    op.add_column("assessments", sa.Column("dispatch_after", sa.Integer()))
    op.add_column("assessments", sa.Column("result_note", sa.Text()))
    op.create_index("ix_assessments_dispatch_after", "assessments", ["dispatch_after"])


def downgrade():
    op.drop_index("ix_assessments_dispatch_after", table_name="assessments")
    for column in ("result_note", "dispatch_after", "submitted_version"):
        op.drop_column("assessments", column)
