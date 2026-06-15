@echo off
title AI Demo System

echo ========================================
echo        AI Demo System - Starting...
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check .env
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [INFO] .env created from .env.example
        echo [INFO] Please edit .env to fill in OPENAI_API_KEY, then re-run this script.
        notepad .env
        pause
        exit /b 0
    ) else (
        echo [ERROR] .env.example not found. Project files may be incomplete.
        pause
        exit /b 1
    )
)

REM Create venv
if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
)

REM Activate venv and install dependencies
echo [2/4] Installing dependencies (first run takes a few minutes)...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

REM Create log directory
if not exist "logs" mkdir logs

REM Start MCP Server
echo [3/4] Starting MCP Server...
start /b "" python -m mcp_server.server > logs\mcp_server.log 2>&1
timeout /t 3 /nobreak >nul

REM Start API Server
echo [4/4] Starting API Server...
start /b "" uvicorn api.app:app --host 0.0.0.0 --port 8000 > logs\api_server.log 2>&1
timeout /t 2 /nobreak >nul

REM Open browser
echo.
echo ========================================
echo  System is up. Opening browser...
echo  URL: http://localhost:8000
echo ========================================
echo.
start http://localhost:8000

echo Press any key to stop all services and exit...
pause >nul

REM Stop services
echo Stopping services...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo All services stopped. Bye!
exit /b 0
