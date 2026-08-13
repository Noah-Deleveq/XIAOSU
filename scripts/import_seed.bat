@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"
echo 导入种子文档到知识库...
for %%f in (seed_docs\*.md seed_docs\*.txt seed_docs\*.pdf seed_docs\*.docx) do (
    echo   - %%~nxf
    curl -s -F "file=@%%f" http://localhost:8000/api/docs
    echo.
)
echo.
echo 完成！现在可以去钉钉 @小苏 提问了。
pause
