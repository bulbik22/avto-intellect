import os
import time

from celery import Celery
from fastapi import HTTPException
from sqlalchemy import select, update

from .dependencies import Sessions
from .models import Assessment, Photo
from .photos import BUCKET, objects


app = Celery("estimate", broker=os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"))
app.conf.update(
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    beat_schedule={"dispatch-assessments": {"task": "estimate.dispatch", "schedule": 2.0,
                                            "options": {"expires": 5}}},
)


@app.task(name="estimate.dispatch")
def dispatch():
    now = int(time.time())
    with Sessions.begin() as db:
        # Keep requests in SQL until completion. A lost broker message or crashed
        # worker becomes eligible for dispatch again after the lease expires.
        due = db.scalars(select(Assessment).where(Assessment.dispatch_after <= now)
                         .order_by(Assessment.dispatch_after).limit(50)
                         .with_for_update(skip_locked=True)).all()
        messages = [(row.assessment_id, row.version) for row in due]
        for row in due:
            row.dispatch_after = now + 30
    for assessment_id, version in messages:
        prepare.delay(assessment_id, version)


def inspect_inputs(description, photos):
    if photos:
        with objects() as client:
            for photo in photos:
                info = client.stat_object(BUCKET, photo.object_key)
                if info.size != photo.size:
                    return "error", "Размер сохранённого фото изменился. Удалите его и загрузите снова."
    words = description.casefold().strip(" .!?").split()
    if not photos and (len(words) < 2 or " ".join(words) in {"удар спереди", "удар сзади", "после дтп"}):
        return "needs_clarification", "Укажите повреждённую деталь и что с ней произошло или добавьте фото."
    parts = []
    if description.strip():
        parts.append("описание")
    if photos:
        parts.append(f"фото — {len(photos)}")
    return "ready", "Получено: " + ", ".join(parts) + "."


@app.task(name="estimate.prepare", acks_late=True, reject_on_worker_lost=True)
def prepare(assessment_id, version):
    active = (Assessment.assessment_id == assessment_id, Assessment.version == version,
              Assessment.status.in_(("queued", "processing")))
    with Sessions.begin() as db:
        if not db.execute(update(Assessment).where(*active).values(status="processing")).rowcount:
            return
    with Sessions.begin() as db:
        # Reclaim only this generation. The write lock also serializes redelivery
        # on SQLite, where SELECT FOR UPDATE is ignored.
        row = db.scalar(update(Assessment).where(*active).values(status="processing")
                        .returning(Assessment))
        if row is None:
            return
        photos = db.scalars(select(Photo).where(Photo.assessment_id == assessment_id,
                                                Photo.ready.is_(True))).all()
        try:
            row.status, row.result_note = inspect_inputs(row.description, photos)
        except HTTPException:
            row.status = "error"
            row.result_note = "Не удалось прочитать фотографии из хранилища. Повторите запуск."
        row.dispatch_after = None
