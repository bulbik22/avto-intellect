from pathlib import Path
import os
import secrets
from alembic import command
from alembic.config import Config
import uvicorn

root = Path(__file__).resolve().parent
key_file = root / ".local-secret"
if "AUTH_SECRET" not in os.environ:
    if not key_file.exists():
        with key_file.open("x", encoding="ascii") as output:
            output.write(secrets.token_hex(32))
    os.environ["AUTH_SECRET"] = key_file.read_text(encoding="ascii").strip()

if __name__ == "__main__":
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    command.upgrade(Config(str(root / "alembic.ini"), ini_section="estimate"), "head")
    from fastapi import FastAPI
    from services.estimate.main import api as estimate_api
    from fastapi.staticfiles import StaticFiles
    from services.users.main import api as users_api

    app = FastAPI(title="Авто-Интеллект")
    app.include_router(users_api)
    app.include_router(estimate_api)
    app.mount("/", StaticFiles(directory=root.parent / "frontend", html=True), name="frontend")
    uvicorn.run(app, host="127.0.0.1", port=8000)
