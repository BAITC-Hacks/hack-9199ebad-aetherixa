"""
Запуск: uvicorn app.main:app --reload
Документация Swagger откроется на http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()  # подхватывает .env, если он создан из .env.example

from app.database import Base, SessionLocal, engine
from app.seed import seed_if_empty
from app.routers import ai, boss, quests, responses, shop, tasks, teams


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AI Sana: Город решений — API",
    description="Каталог бизнес-задач с рейтингом готовности, откликами команд, "
                 "маршрутом миссии, мастерской и финальной проверкой.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(tasks.router)
app.include_router(responses.router)
app.include_router(quests.router)
app.include_router(boss.router)
app.include_router(teams.router)
app.include_router(shop.router)
app.include_router(ai.router)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "docs": "/docs"}
