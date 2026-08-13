@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"
echo [1/2] Stopping old Xiaosu on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":8000 " ^| findstr /C:"LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul
if not exist .venv (
    echo [ERROR] .venv not found. Run: uv sync
    pause
    exit /b 1
)
echo ==========================================
echo   Xiaosu AI - HTTP + DingTalk + Feishu
echo ==========================================
echo [2/2] Starting Xiaosu...
call .venv\Scripts\activate.bat
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
