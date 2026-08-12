@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"
echo ==========================================
echo  小苏 AI 助手 · 一键启动（HTTP + 钉钉机器人）
echo ==========================================
call .venv\Scripts\activate.bat
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
