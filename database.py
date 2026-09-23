"""
Подключение к базе данных. По умолчанию — файл SQLite рядом с проектом,
этого достаточно для хакатона и не требует установки отдельной СУБД.
Чтобы переключиться на PostgreSQL/MySQL, замените DATABASE_URL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./aisana.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # нужно для SQLite + FastAPI
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency для FastAPI: одна сессия на запрос, закрывается автоматически."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
