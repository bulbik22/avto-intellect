import hashlib
import hmac
import os
import secrets
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker

from .models import Account, Base, Code, LoginSession, Vehicle


ROOT = Path(__file__).resolve().parents[2]
engine = create_engine(os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'local.db'}"))
KEY = os.environ.get("AUTH_SECRET")
if not KEY:
    raise RuntimeError("Задайте AUTH_SECRET перед запуском")
app = FastAPI(title="Авто-Интеллект")
api = APIRouter(prefix="/api/v1")

Sessions = sessionmaker(engine)
upsert = {"postgresql": pg_insert, "sqlite": sqlite_insert}[engine.dialect.name]
Base.metadata.create_all(engine)


class Address(BaseModel):
    email: EmailStr


class Credentials(Address):
    password: str = Field(min_length=8, max_length=128)


class Confirmation(Address):
    code: str = Field(pattern=r"^[0-9]{6}$")


class Reset(Confirmation):
    password: str = Field(min_length=8, max_length=128)


class Car(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1886, le=date.today().year + 1)
    mileage_km: int = Field(ge=0, le=9999999)
    region: str = Field(min_length=1, max_length=120)


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def encode_password(password):
    salt = secrets.token_hex(16)
    return salt + ":" + password_hash(password, salt)


def digest(email, purpose, code):
    return hmac.digest(KEY.encode(), f"{email}|{purpose}|{code}".encode(), "sha256").hex()


def issue(db, email, purpose):
    now = int(time.time())
    code = f"{secrets.randbelow(1000000):06}"
    statement = upsert(Code).values(
        email=email, purpose=purpose, digest=digest(email, purpose, code),
        expires=now + 600, attempts=5,
    )
    result = db.execute(statement.on_conflict_do_update(
        index_elements=[Code.email, Code.purpose],
        set_={"digest": statement.excluded.digest, "expires": statement.excluded.expires, "attempts": 5},
        where=Code.expires <= now + 540,
    ).returning(Code.email))
    if result.scalar_one_or_none() is not None:
        print(f"Локальная почта | {email} | {purpose} | {code}", flush=True)


def consume(db, email, purpose, code):
    active = (Code.email == email, Code.purpose == purpose, Code.attempts > 0)
    consumed = db.scalar(delete(Code).where(
        *active, Code.expires > int(time.time()), Code.digest == digest(email, purpose, code)
    ).returning(Code.email))
    if consumed is not None:
        return True
    db.execute(update(Code).where(*active).values(attempts=Code.attempts - 1))
    return False


@api.post("/auth/register", status_code=202)
def register(body: Credentials):
    email = body.email.lower()
    with Sessions.begin() as db:
        db.execute(upsert(Account).values(
            id=str(uuid4()), email=email, password=encode_password(body.password)
        ).on_conflict_do_nothing(index_elements=[Account.email]))
        if not db.scalar(select(Account.confirmed).where(Account.email == email)):
            issue(db, email, "confirm")
    return {"message": "Проверьте код подтверждения"}


@api.post("/auth/confirm")
def confirm(body: Reset):
    email = body.email.lower()
    with Sessions.begin() as db:
        ok = consume(db, email, "confirm", body.code)
        if ok:
            db.execute(update(Account).where(Account.email == email, Account.confirmed == 0)
                       .values(confirmed=1, password=encode_password(body.password)))
    if not ok:
        raise HTTPException(400, "Код недействителен")
    return {"confirmed": True}


@api.post("/auth/recovery", status_code=202)
def recover(body: Address):
    email = body.email.lower()
    with Sessions.begin() as db:
        if db.scalar(select(Account.confirmed).where(Account.email == email)):
            issue(db, email, "reset")
    return {"message": "Если аккаунт существует, код выпущен"}


@api.post("/auth/reset-password")
def reset(body: Reset):
    email = body.email.lower()
    with Sessions.begin() as db:
        ok = consume(db, email, "reset", body.code)
        if ok:
            account = db.scalar(select(Account).where(Account.email == email))
            account.password = encode_password(body.password)
            db.execute(delete(LoginSession).where(LoginSession.account == account.id))
    if not ok:
        raise HTTPException(400, "Код недействителен")
    return {"updated": True}


@api.post("/auth/login")
def login(body: Credentials, response: Response):
    with Sessions.begin() as db:
        account = db.scalar(select(Account).where(Account.email == body.email.lower()))
        if not account or not account.confirmed:
            raise HTTPException(401, "Проверьте email, пароль и подтверждение регистрации")
        salt, stored = account.password.split(":")
        if not hmac.compare_digest(stored, password_hash(body.password, salt)):
            raise HTTPException(401, "Проверьте email и пароль")
        sid = str(uuid4())
        exp = int(time.time()) + 3600
        db.add(LoginSession(id=sid, account=account.id, expires=exp))
        token = jwt.encode(dict(sub=account.id, jti=sid, exp=exp), KEY, algorithm="HS256")
    response.set_cookie("session", token, max_age=3600, httponly=True, samesite="strict",
                        secure=os.getenv("HTTPS_ONLY") == "1")
    return {"authenticated": True}


def identity(request: Request):
    try:
        claims = jwt.decode(request.cookies.get("session", ""), KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Войдите в аккаунт")
    with Sessions() as db:
        owner = db.scalar(select(LoginSession.account).where(
            LoginSession.id == claims["jti"], LoginSession.expires > int(time.time())
        ))
    if owner != claims["sub"]:
        raise HTTPException(401, "Сессия истекла")
    return owner, claims["jti"]


@api.post("/auth/logout")
def logout(response: Response, user=Depends(identity)):
    with Sessions.begin() as db:
        db.execute(delete(LoginSession).where(LoginSession.id == user[1]))
    response.delete_cookie("session")
    return {"authenticated": False}


@api.get("/users/me")
def profile(user=Depends(identity)):
    with Sessions() as db:
        account = db.get(Account, user[0])
        return {"id": account.id, "email": account.email}


class SavedCar(Car):
    id: str


@api.post("/cars", status_code=201, response_model=SavedCar)
def add_car(car: Car, user=Depends(identity)):
    car_id = str(uuid4())
    with Sessions.begin() as db:
        db.add(Vehicle(**car.model_dump(), owner=user[0], id=car_id))
    return SavedCar(id=car_id, **car.model_dump())


@api.get("/cars", response_model=list[SavedCar])
def cars(user=Depends(identity)):
    with Sessions() as db:
        return db.scalars(select(Vehicle).where(Vehicle.owner == user[0])).all()


@api.get("/cars/{car_id}", response_model=SavedCar)
def find_car(car_id: str, user=Depends(identity)):
    with Sessions() as db:
        car = db.scalar(select(Vehicle).where(Vehicle.owner == user[0], Vehicle.id == car_id))
        if car is None:
            raise HTTPException(404, "Автомобиль не найден")
        return car


app.include_router(api)
app.mount("/",StaticFiles(directory=ROOT.parent / "frontend",html=True),name="frontend")


