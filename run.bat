@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Crie o venv: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    exit /b 1
)
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
