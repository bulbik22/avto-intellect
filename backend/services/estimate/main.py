from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .dependencies import Sessions, engine, owner, users_get
from .photos import photos_api
from .models import Assessment, Photo


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
    result_note: str | None
    status: str
    version: int


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
def list_drafts(include_history: bool = False, account=Depends(owner)):
    with Sessions() as db:
        query = select(Assessment).where(Assessment.owner == account)
        if not include_history:
            query = query.where(Assessment.status == "draft")
        return db.scalars(query.order_by(Assessment.assessment_id)).all()


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
            *owned, Assessment.status.in_(("draft", "needs_clarification", "error")), Assessment.version == body.version
        ).values(description=body.description, version=Assessment.version + 1).returning(Assessment))
        if draft is not None:
            return Draft.model_validate(draft, from_attributes=True)
        if not db.scalar(select(Assessment.assessment_id).where(*owned)):
            raise HTTPException(404, "Заявка не найдена")
        raise HTTPException(409, "Заявка уже изменилась. Обновите страницу перед сохранением.")


@api.post("/{assessment_id}/calculate", response_model=Draft, status_code=202)
def calculate(assessment_id: UUID, body: EditDraft, account=Depends(owner)):
    with Sessions.begin() as db:
        owned = (Assessment.assessment_id == str(assessment_id), Assessment.owner == account)
        # Take the same write lock as photo mutations, including on SQLite.
        row = db.scalar(update(Assessment).where(*owned).values(status=Assessment.status)
                        .returning(Assessment))
        if row is None:
            raise HTTPException(404, "Заявка не найдена")
        if row.submitted_version == body.version and row.description == body.description:
            return Draft.model_validate(row, from_attributes=True)
        if row.status not in ("draft", "needs_clarification", "error") or row.version != body.version:
            raise HTTPException(409, "Заявка уже изменилась. Обновите страницу.")
        photos = db.scalars(select(Photo.ready).where(Photo.assessment_id == row.assessment_id)).all()
        if not body.description.strip() and not any(photos):
            raise HTTPException(422, "Добавьте описание или хотя бы одну фотографию.")
        row.description = body.description
        row.submitted_version = row.version
        row.version += 1
        row.status = "queued"
        row.dispatch_after = 0
        row.result_note = None
        return Draft.model_validate(row, from_attributes=True)


api.include_router(photos_api)

app = FastAPI(title="Авто-Интеллект — оценка")
app.include_router(api)
