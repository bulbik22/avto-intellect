from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {str: Text}


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    confirmed: Mapped[int] = mapped_column(server_default="0")


class Code(Base):
    __tablename__ = "codes"

    email: Mapped[str] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(primary_key=True)
    digest: Mapped[str]
    expires: Mapped[int] = mapped_column(BigInteger)
    attempts: Mapped[int]


class LoginSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(primary_key=True)
    refresh_digest: Mapped[str | None]
    account: Mapped[str]
    expires: Mapped[int] = mapped_column(BigInteger)


class Vehicle(Base):
    __tablename__ = "cars"

    id: Mapped[str] = mapped_column(primary_key=True)
    owner: Mapped[str]
    make: Mapped[str]
    model: Mapped[str]
    year: Mapped[int]
    mileage_km: Mapped[int]
    region: Mapped[str]
