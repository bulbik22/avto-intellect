from alembic import context
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema

from services.users.database import users_engine
from services.users.models import Base


engine = users_engine()
with engine.begin() as connection:
    postgres = connection.dialect.name == "postgresql"
    if postgres:
        # Serialize simultaneous service starts, including version table creation.
        connection.execute(text("SELECT pg_advisory_xact_lock(1096176719, 1)"))
        connection.execute(CreateSchema("users", if_not_exists=True))
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
    )
    context.run_migrations()
