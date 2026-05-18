from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

_url = str(settings.DATABASE_URL or "").lower()
_is_pg = "postgresql" in _url

if _is_pg:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=40,
        pool_recycle=1800,
        pool_timeout=30,
        echo=False,
        connect_args={
            "connect_timeout": 10,
            "application_name": "token_shop_backend",
        },
    )
else:
    # SQLite (tests / local): no server-side pool knobs
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
