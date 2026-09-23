"""Run with: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import models before create_all: SQLAlchemy must know every table.
from app.database import Base, PROJECT_ROOT, SessionLocal, engine
from app import models  # noqa: F401
from app import ui_models  # noqa: F401
from app.seed import seed_if_empty
from app.ui_seed import seed_ui_modes
from app.migrations import migrate_existing_schema
from app.routers import ai, boss, quests, responses, shop, tasks, teams, ui


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_existing_schema(engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if os.getenv('SEED_DEMO', 'true').lower() in ('1', 'true', 'yes'):
            seed_if_empty(db)
        seed_ui_modes(db)
    finally:
        db.close()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="AI Sana: Город решений — API",
    description="Каталог бизнес-задач с AI-уточнением, рейтингом и откликами команд.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(tasks.router)
app.include_router(responses.router)
app.include_router(quests.router)
app.include_router(boss.router)
app.include_router(teams.router)
app.include_router(shop.router)
app.include_router(ai.router)
app.include_router(ui.router)
app.mount('/static', StaticFiles(directory=PROJECT_ROOT / 'frontend' / 'static'), name='static')


@app.get('/', include_in_schema=False)
def website():
    return FileResponse(PROJECT_ROOT / 'frontend' / 'templates' / 'index.html',
                        headers={'Cache-Control': 'no-cache'})


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "docs": "/docs", "website": "/"}


@app.get('/api/config', tags=['settings'])
def public_configuration():
    configured = bool(os.getenv('AI_API_KEY', '').strip()) and os.getenv('AI_FORCE_FALLBACK', '').lower() not in ('true', '1', 'yes')
    return {'demo_mode': True, 'ai_configured': configured,
            'database': engine.dialect.name}
