"""Совместимая точка создания ЕДИНОЙ схемы backend.

Старая отдельная схема заменена: таблицы определяются только в app/models.py
и app/ui_models.py. Приложение вызывает тот же код автоматически при запуске.
"""
import os

from app.database import Base, SessionLocal, engine
from app import models, ui_models
from app.migrations import migrate_existing_schema
from app.seed import seed_if_empty
from app.ui_seed import seed_ui_modes


def init_db():
    migrate_existing_schema(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if os.getenv('SEED_DEMO', 'true').lower() in ('true', '1', 'yes'):
            seed_if_empty(db)
        seed_ui_modes(db)
    print('Единая схема backend готова. Запуск: python -m uvicorn app.main:app --reload')


if __name__ == '__main__':
    init_db()
