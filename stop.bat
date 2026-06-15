@echo off
echo 正在停止 AI Demo System...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo 已停止所有服务。
pause
