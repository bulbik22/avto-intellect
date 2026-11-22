import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def service_engine(schema):
    backend = Path(__file__).resolve().parents[1]
    filename = "local.db" if schema == "users" else "estimate.db"
    url = make_url(os.getenv("DATABASE_URL", f"sqlite:///{backend / filename}"))
    options = {"options": f"-csearch_path={schema}"} if url.get_backend_name() == "postgresql" else {}
    return create_engine(url, connect_args=options)
