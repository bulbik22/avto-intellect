"""Adopt existing users tables or create the initial schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_users"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ("accounts", "codes", "sessions", "cars")


def upgrade():
    connection = op.get_bind()
    postgres = connection.dialect.name == "postgresql"
    schema = "users" if postgres else None
    inspector = sa.inspect(connection)
    existing = set(inspector.get_table_names(schema=schema))
    legacy = set(inspector.get_table_names(schema="public")) if postgres else set()
    for name in TABLES:
        if name in legacy:
            if name in existing:
                raise RuntimeError(f"Both public.{name} and users.{name} exist")
            op.execute(f'ALTER TABLE public."{name}" SET SCHEMA users')
            existing.add(name)

    if "accounts" not in existing:
        op.create_table(
            "accounts",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("email", sa.Text(), nullable=False, unique=True),
            sa.Column("password", sa.Text(), nullable=False),
            sa.Column("confirmed", sa.Integer(), nullable=False, server_default="0"),
            schema=schema,
        )
    if "codes" not in existing:
        op.create_table(
            "codes",
            sa.Column("email", sa.Text(), primary_key=True),
            sa.Column("purpose", sa.Text(), primary_key=True),
            sa.Column("digest", sa.Text(), nullable=False),
            sa.Column("expires", sa.BigInteger(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            schema=schema,
        )
    if "sessions" not in existing:
        op.create_table(
            "sessions",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("account", sa.Text(), nullable=False),
            sa.Column("expires", sa.BigInteger(), nullable=False),
            schema=schema,
        )
    if "cars" not in existing:
        op.create_table(
            "cars",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("owner", sa.Text(), nullable=False),
            sa.Column("make", sa.Text(), nullable=False),
            sa.Column("model", sa.Text(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("mileage_km", sa.Integer(), nullable=False),
            sa.Column("region", sa.Text(), nullable=False),
            schema=schema,
        )


def downgrade():
    # Restore the pre-Alembic layout and retain the user's data.
    if op.get_bind().dialect.name == "postgresql":
        for name in TABLES:
            op.execute(f'ALTER TABLE users."{name}" SET SCHEMA public')
