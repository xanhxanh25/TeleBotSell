from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Tối ưu connection pool cho performance
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,  # Tăng pool size
    max_overflow=20,  # Cho phép overflow
    pool_recycle=3600,  # Recycle connections sau 1h
    echo=False,  # Tắt SQL logging để tăng tốc
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
