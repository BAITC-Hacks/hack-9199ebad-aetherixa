@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Create .venv and install requirements.txt first.
    pause
    exit /b 1
)
echo Website: http://127.0.0.1:8000/
echo API docs: http://127.0.0.1:8000/docs
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
