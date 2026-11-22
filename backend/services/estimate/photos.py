import hashlib
import io
import os
import time
from contextlib import contextmanager
from functools import lru_cache
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from minio import Minio
from minio.error import MinioException, S3Error
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import func, select, update
from urllib3 import PoolManager, Timeout
from urllib3.exceptions import HTTPError

from .dependencies import Sessions, owner
from .models import Assessment, Photo


photos_api = APIRouter()
BUCKET = "damage-photos"
MAX_BYTES = 8 * 1024 * 1024
MEDIA = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class PhotoInfo(BaseModel):
    photo_id: str
    media_type: str
    size: int


@lru_cache(maxsize=1)
def storage():
    password = os.getenv("MINIO_ROOT_PASSWORD")
    if not password:
        raise HTTPException(503, "Не настроено хранилище фотографий")
    client = Minio(os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000"),
                   access_key=os.getenv("MINIO_ROOT_USER", "avto"), secret_key=password,
                   secure=False, http_client=PoolManager(timeout=Timeout(connect=3, read=15), retries=False))
    if not client.bucket_exists(BUCKET):
        try:
            client.make_bucket(BUCKET)
        except S3Error as exc:
            if exc.code != "BucketAlreadyOwnedByYou":
                raise
    return client


@contextmanager
def objects():
    try:
        yield storage()
    except (MinioException, HTTPError, OSError):
        raise HTTPException(503, "Хранилище фотографий временно недоступно") from None


def require_access(db, draft_id, account, *, editing=False):
    owned = (Assessment.assessment_id == draft_id, Assessment.owner == account)
    if editing:
        # Serialize photo mutations per draft on PostgreSQL and on local SQLite.
        status = db.scalar(update(Assessment).where(*owned).values(status=Assessment.status)
                           .returning(Assessment.status))
    else:
        status = db.scalar(select(Assessment.status).where(*owned))
    if status is None:
        raise HTTPException(404, "Заявка не найдена")
    if editing and status != "draft":
        raise HTTPException(409, "Фотографии можно менять только в черновике")


def image_type(data):
    try:
        with Image.open(io.BytesIO(data), formats=list(MEDIA)) as image:
            if image.width * image.height > 32_000_000 or getattr(image, "is_animated", False):
                raise HTTPException(422, "Выберите неподвижное фото до 32 мегапикселей")
            media_type = MEDIA[image.format]
            image.verify()
        with Image.open(io.BytesIO(data), formats=list(MEDIA)) as image:
            image.load()
        return media_type
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(422, "Нужен исправный файл JPEG, PNG или WebP") from None


def visible_photos(draft_id):
    return select(Photo).where(Photo.assessment_id == draft_id, Photo.ready.is_(True))


@photos_api.get("/{assessment_id}/photos", response_model=list[PhotoInfo])
def list_photos(assessment_id: UUID, account=Depends(owner)):
    with Sessions() as db:
        require_access(db, str(assessment_id), account)
        return db.scalars(visible_photos(str(assessment_id)).order_by(Photo.created, Photo.photo_id)).all()


@photos_api.post("/{assessment_id}/photos", response_model=PhotoInfo)
def add_photo(assessment_id: UUID, file: UploadFile, account=Depends(owner)):
    draft_id = str(assessment_id)
    with Sessions() as db:
        require_access(db, draft_id, account)
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Максимальный размер фотографии — 8 МБ")
    media_type = image_type(data)
    photo_id = str(uuid5(assessment_id, hashlib.sha256(data).hexdigest()))
    now = int(time.time())
    with Sessions.begin() as db:
        require_access(db, draft_id, account, editing=True)
        existing = db.get(Photo, photo_id)
        if existing and existing.ready:
            return PhotoInfo.model_validate(existing, from_attributes=True)
        count = db.scalar(select(func.count()).select_from(Photo).where(
            Photo.assessment_id == draft_id, Photo.ready.is_(True)
        ))
        if count >= 6:
            raise HTTPException(409, "К заявке можно прикрепить до шести фотографий")
        # Keep the object key in SQL across failures between the two stores.
        # On the next upload, reclaim abandoned reservations and pending deletions.
        stale = db.scalars(select(Photo).where(Photo.assessment_id == draft_id,
            Photo.ready.is_(False), Photo.photo_id != photo_id, Photo.created < now - 600)).all()
        for photo in stale:
            with objects() as client:
                client.remove_object(BUCKET, photo.object_key)
            db.delete(photo)
        if existing:
            existing.created = now
        else:
            db.add(Photo(photo_id=photo_id, assessment_id=draft_id, media_type=media_type,
                         size=len(data), object_key=f"{draft_id}/{photo_id}", ready=False, created=now))

    with Sessions.begin() as db:
        require_access(db, draft_id, account, editing=True)
        photo = db.get(Photo, photo_id)
        if photo is None:
            raise HTTPException(409, "Фото было удалено. Повторите загрузку.")
        if not photo.ready:
            if len(db.scalars(visible_photos(draft_id)).all()) >= 6:
                # A prior interrupted upload may already have written this key.
                with objects() as client:
                    client.remove_object(BUCKET, photo.object_key)
                db.delete(photo)
            else:
                with objects() as client:
                    client.put_object(BUCKET, photo.object_key, io.BytesIO(data), len(data), content_type=media_type)
                photo.ready = True
        if photo.ready:
            return PhotoInfo.model_validate(photo, from_attributes=True)
    raise HTTPException(409, "К заявке можно прикрепить до шести фотографий")


@photos_api.get("/{assessment_id}/photos/{photo_id}")
def download(assessment_id: UUID, photo_id: UUID, account=Depends(owner)):
    with Sessions() as db:
        require_access(db, str(assessment_id), account)
        photo = db.scalar(visible_photos(str(assessment_id)).where(Photo.photo_id == str(photo_id)))
        if photo is None:
            raise HTTPException(404, "Фото не найдено")
        with objects() as client:
            obj = client.get_object(BUCKET, photo.object_key)
            try:
                return Response(obj.read(), media_type=photo.media_type,
                                headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
            finally:
                obj.close()
                obj.release_conn()


@photos_api.delete("/{assessment_id}/photos/{photo_id}", status_code=204)
def remove_photo(assessment_id: UUID, photo_id: UUID, account=Depends(owner)):
    draft_id = str(assessment_id)
    with Sessions.begin() as db:
        require_access(db, draft_id, account, editing=True)
        photo = db.get(Photo, str(photo_id))
        if photo is None or photo.assessment_id != draft_id:
            return Response(status_code=204)
        photo.ready = False
        photo.created = int(time.time())
    with Sessions.begin() as db:
        require_access(db, draft_id, account, editing=True)
        photo = db.get(Photo, str(photo_id))
        if photo and not photo.ready:
            with objects() as client:
                client.remove_object(BUCKET, photo.object_key)
            db.delete(photo)
    return Response(status_code=204)
