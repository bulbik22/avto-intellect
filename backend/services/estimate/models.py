from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {str: Text}


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        Index("one_draft_per_car", "car_id", unique=True,
              postgresql_where=text("status = 'draft'"), sqlite_where=text("status = 'draft'")),
    )

    assessment_id: Mapped[str] = mapped_column(primary_key=True)
    car_id: Mapped[str]
    owner: Mapped[str] = mapped_column(index=True)
    status: Mapped[str]
    description: Mapped[str]
    version: Mapped[int]


class Photo(Base):
    __tablename__ = "photos"

    photo_id: Mapped[str] = mapped_column(primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.assessment_id"), index=True)
    object_key: Mapped[str]
    media_type: Mapped[str]
    size: Mapped[int]
    created: Mapped[int]
    ready: Mapped[bool]
