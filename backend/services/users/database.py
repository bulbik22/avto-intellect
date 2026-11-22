import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


def users_engine():
    url = make_url(os.environ.get("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'local.db'}"))
    options = {"options": "-csearch_path=users"} if url.get_backend_name() == "postgresql" else {}
    return create_engine(url, connect_args=options)
