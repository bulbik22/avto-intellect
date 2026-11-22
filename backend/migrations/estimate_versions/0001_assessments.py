"""Create assessment drafts in the estimate schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_assessments"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assessments",
        sa.Column("assessment_id", sa.Text(), primary_key=True),
        sa.Column("car_id", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_assessments_owner", "assessments", ["owner"])
    op.create_index("one_draft_per_car", "assessments", ["car_id"], unique=True,
                    postgresql_where=sa.text("status = 'draft'"), sqlite_where=sa.text("status = 'draft'"))


def downgrade():
    op.drop_table("assessments")
