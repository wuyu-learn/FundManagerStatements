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
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.9+ is required for the default app.
    python --version
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
) else (
    .venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Existing .venv is not Python 3.9+.
        echo Delete .venv and re-run start.bat.
        pause
        exit /b 1
    )
)

REM Activate venv and install dependencies
echo [2/4] Installing dependencies (first run takes a few minutes)...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

REM Create log directory
if not exist "logs" mkdir logs

REM Load selected .env options used by this script
set API_PORT=8000
set ENABLE_MCP_SERVER=false
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if "%%A"=="API_PORT" set API_PORT=%%B
    if "%%A"=="ENABLE_MCP_SERVER" set ENABLE_MCP_SERVER=%%B
)

REM Start optional MCP Server
if /i "%ENABLE_MCP_SERVER%"=="true" (
    .venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] ENABLE_MCP_SERVER=true requires Python 3.11+.
        echo Disable ENABLE_MCP_SERVER or recreate .venv with Python 3.11+.
        pause
        exit /b 1
    )
    pip install -r requirements-mcp.txt -q
    echo [3/4] Starting MCP Server optional external tool endpoint...
    start /b "" python -m mcp_server.server > logs\mcp_server.log 2>&1
    timeout /t 3 /nobreak >nul
) else (
    echo [3/4] Skipping MCP Server. Agent calls skills directly.
)

REM Start API Server
echo [4/4] Starting API Server...
start /b "" uvicorn api.app:app --host 127.0.0.1 --port %API_PORT% > logs\api_server.log 2>&1
timeout /t 2 /nobreak >nul

REM Open browser
echo.
echo ========================================
echo  System is up. Opening browser...
echo  URL: http://localhost:%API_PORT%
echo ========================================
echo.
start http://localhost:%API_PORT%

echo Press any key to stop all services and exit...
pause >nul

REM Stop services
echo Stopping services...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo All services stopped. Bye!
exit /b 0
