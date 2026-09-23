@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Create .venv and install requirements.txt first.
    pause
    exit /b 1
)
set "DATABASE_URL=sqlite:///./aisana-demo.db"
set "AI_API_KEY="
set "AI_FORCE_FALLBACK=true"
set "SEED_DEMO=true"
echo LOCAL DEMO: SQLite database aisana-demo.db, not SQL Server.
echo Website: http://127.0.0.1:8000/
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
endlocal
