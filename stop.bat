@echo off
echo Stopping AI Demo System...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo All services stopped.
pause
