from pathlib import Path
import os
import secrets
import uvicorn

root = Path(__file__).resolve().parent
key_file = root / ".local-secret"
if "AUTH_SECRET" not in os.environ:
    if not key_file.exists():
        with key_file.open("x", encoding="ascii") as output:
            output.write(secrets.token_hex(32))
    os.environ["AUTH_SECRET"] = key_file.read_text(encoding="ascii").strip()

if __name__ == "__main__":
    uvicorn.run("services.users.main:app", host="127.0.0.1", port=8000)
