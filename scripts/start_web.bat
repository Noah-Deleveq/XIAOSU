@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"
echo [1/2] Stopping old Xiaosu on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":8000 " ^| findstr /C:"LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul
start "Xiaosu Backend" cmd /k "call .venv\Scripts\activate.bat && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"
cd /d "%~dp0..\web"
start "Xiaosu Web" cmd /k "pnpm run dev -- --host 0.0.0.0"
timeout /t 6 /nobreak >nul
start http://localhost:5173
