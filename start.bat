@echo off
chcp 65001 >nul
title AI Demo System

echo ========================================
echo        AI Demo System 启动中...
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.11+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 .env
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [提示] 已自动创建 .env 文件
        echo [提示] 请用文本编辑器打开 .env，填写 OPENAI_API_KEY 后重新运行本脚本
        notepad .env
        pause
        exit /b 0
    ) else (
        echo [错误] 未找到 .env.example 文件，请检查项目完整性
        pause
        exit /b 1
    )
)

REM 创建虚拟环境
if not exist ".venv" (
    echo [1/4] 创建虚拟环境...
    python -m venv .venv
)

REM 激活虚拟环境并安装依赖
echo [2/4] 安装依赖（首次运行需要几分钟）...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

REM 创建日志目录
if not exist "logs" mkdir logs

REM 启动 MCP Server
echo [3/4] 启动 MCP Server...
start /b "" python -m mcp_server.server > logs\mcp_server.log 2>&1
timeout /t 3 /nobreak >nul

REM 启动 API Server
echo [4/4] 启动 API Server...
start /b "" uvicorn api.app:app --host 0.0.0.0 --port 8000 > logs\api_server.log 2>&1
timeout /t 2 /nobreak >nul

REM 打开浏览器
echo.
echo ========================================
echo  ✓ 系统已启动！正在打开浏览器...
echo  访问地址：http://localhost:8000
echo ========================================
echo.
start http://localhost:8000

echo 按任意键停止所有服务并退出...
pause >nul

REM 停止服务
echo 正在停止服务...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo 已停止所有服务，再见！
exit /b 0
