from alembic import context
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema

from services.database import service_engine
if context.config.config_ini_section == "estimate":
    from services.estimate.models import Base
    schema = "estimate"
else:
    from services.users.models import Base
    schema = "users"


engine = service_engine(schema)
with engine.begin() as connection:
    postgres = connection.dialect.name == "postgresql"
    if postgres:
        # Serialize simultaneous service starts, including version table creation.
        connection.execute(text("SELECT pg_advisory_xact_lock(1096176719, 1)"))
        connection.execute(CreateSchema(schema, if_not_exists=True))
    context.configure(
        connection=connection,
        version_table="estimate_version" if schema == "estimate" else "alembic_version",
        target_metadata=Base.metadata,
    )
    context.run_migrations()
