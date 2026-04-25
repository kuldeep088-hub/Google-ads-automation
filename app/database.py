from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


def _make_engine():
    kwargs = {}
    if "sqlite" in settings.DATABASE_URL:
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(settings.DATABASE_URL, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
