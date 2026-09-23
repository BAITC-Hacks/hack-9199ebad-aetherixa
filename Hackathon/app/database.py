"""SQL Server connection for the existing AI Sana FastAPI backend."""

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env', override=False)


def _database_url() -> str:
    # Prefer an explicit URL in .env/production.
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        return configured

    server = os.getenv('DB_SERVER', r'DESKTOP-D5H3SMJ\SQLEXPRESS')
    params = quote_plus(
        f"DRIVER={{{os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')}}};"
        f"SERVER={server};"
        f"DATABASE={os.getenv('DB_NAME', 'aetherix_backend')};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return f"mssql+pyodbc:///?odbc_connect={params}"


DATABASE_URL = _database_url()
options = {'pool_pre_ping': True}
if DATABASE_URL.startswith('sqlite'):
    options['connect_args'] = {'check_same_thread': False, 'timeout': 20}
    if ':memory:' in DATABASE_URL or DATABASE_URL in ('sqlite://', 'sqlite+pysqlite://'):
        options['poolclass'] = StaticPool
elif DATABASE_URL.startswith('mssql'):
    options['connect_args'] = {'timeout': 10}
    options['deprecate_large_types'] = True
engine = create_engine(DATABASE_URL, **options)
if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def _foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
