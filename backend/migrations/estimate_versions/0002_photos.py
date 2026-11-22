"""Track private damage photos."""

from alembic import op
import sqlalchemy as sa


revision = "0002_photos"
down_revision = "0001_assessments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "photos",
        sa.Column("photo_id", sa.Text(), primary_key=True),
        sa.Column("assessment_id", sa.Text(), sa.ForeignKey("assessments.assessment_id"), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_photos_assessment_id", "photos", ["assessment_id"])


def downgrade():
    op.drop_table("photos")
