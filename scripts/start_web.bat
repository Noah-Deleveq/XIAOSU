@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"
start "小苏后端(钉钉)" cmd /k "call .venv\Scripts\activate.bat && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"
cd /d "%~dp0..\web"
start "小苏前端" cmd /k "npm run dev -- --host 0.0.0.0"
timeout /t 6 /nobreak >nul
start http://localhost:5173
