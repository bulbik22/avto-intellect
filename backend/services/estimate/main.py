import os
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker

from ..database import service_engine
from .models import Assessment


engine = service_engine("estimate")
Sessions = sessionmaker(engine)
insert = {"postgresql": pg_insert, "sqlite": sqlite_insert}[engine.dialect.name]
api = APIRouter(prefix="/api/v1/assessments")


class CreateDraft(BaseModel):
    car_id: UUID


class EditDraft(BaseModel):
    description: str = Field(max_length=10000)
    version: int = Field(ge=1)


class Draft(BaseModel):
    assessment_id: str
    car_id: str
    description: str
    status: str
    version: int


async def users_get(request, path):
    endpoint = os.getenv("USERS_URL", "http://127.0.0.1:8000")
    try:
        async with httpx.AsyncClient(base_url=endpoint, timeout=5, trust_env=False) as client:
            response = await client.get("/api/v1/" + path, cookies={"session": request.cookies.get("session", "")})
    except httpx.RequestError:
        raise HTTPException(503, "Сервис пользователей временно недоступен") from None
    if response.status_code == 401:
        raise HTTPException(401, "Войдите в аккаунт")
    if response.status_code == 404:
        raise HTTPException(404, "Автомобиль не найден")
    if response.status_code != 200:
        raise HTTPException(503, "Сервис пользователей временно недоступен")
    return response.json()


async def owner(request: Request):
    return (await users_get(request, "users/me"))["id"]


async def owned_car(body: CreateDraft, request: Request):
    return (await users_get(request, f"cars/{body.car_id}"))["id"]


@api.post("", response_model=Draft)
def open_draft(car_id=Depends(owned_car), account=Depends(owner)):
    with Sessions.begin() as db:
        db.execute(insert(Assessment).values(
            assessment_id=str(uuid4()), car_id=car_id, owner=account, status="draft",
            description="", version=1,
        ).on_conflict_do_nothing())
        draft = db.scalars(select(Assessment).where(
            Assessment.owner == account, Assessment.car_id == car_id, Assessment.status == "draft"
        )).one()
        return Draft.model_validate(draft, from_attributes=True)


@api.get("", response_model=list[Draft])
def list_drafts(account=Depends(owner)):
    with Sessions() as db:
        return db.scalars(select(Assessment).where(
            Assessment.owner == account, Assessment.status == "draft"
        )).all()


@api.get("/{assessment_id}", response_model=Draft)
def read_draft(assessment_id: UUID, account=Depends(owner)):
    with Sessions() as db:
        draft = db.scalar(select(Assessment).where(
            Assessment.assessment_id == str(assessment_id), Assessment.owner == account
        ))
        if draft is None:
            raise HTTPException(404, "Заявка не найдена")
        return draft


@api.patch("/{assessment_id}", response_model=Draft)
def edit_draft(assessment_id: UUID, body: EditDraft, account=Depends(owner)):
    owned = (Assessment.assessment_id == str(assessment_id), Assessment.owner == account)
    with Sessions.begin() as db:
        draft = db.scalar(update(Assessment).where(
            *owned, Assessment.status == "draft", Assessment.version == body.version
        ).values(description=body.description, version=Assessment.version + 1).returning(Assessment))
        if draft is not None:
            return Draft.model_validate(draft, from_attributes=True)
        if not db.scalar(select(Assessment.assessment_id).where(*owned)):
            raise HTTPException(404, "Заявка не найдена")
        raise HTTPException(409, "Заявка уже изменилась. Обновите страницу перед сохранением.")


app = FastAPI(title="Авто-Интеллект — оценка")
app.include_router(api)
