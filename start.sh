#!/bin/bash

echo "========================================"
echo "       AI Demo System 启动中..."
echo "========================================"
echo ""

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python3，请先安装 Python 3.11+"
    echo "Mac 安装命令：brew install python3"
    exit 1
fi

# 检查 .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[提示] 已自动创建 .env 文件"
        echo "[提示] 请编辑 .env 文件，填写 OPENAI_API_KEY 后重新运行"
        echo "编辑命令：open .env 或 nano .env"
        exit 0
    else
        echo "[错误] 未找到 .env.example 文件，请检查项目完整性"
        exit 1
    fi
fi

# 创建日志目录
mkdir -p logs

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活并安装依赖
echo "[2/4] 安装依赖（首次运行需要几分钟）..."
source .venv/bin/activate
pip install -r requirements.txt -q

# 停止函数
cleanup() {
    echo ""
    echo "正在停止服务..."
    if [ -f logs/mcp_server.pid ]; then
        kill $(cat logs/mcp_server.pid) 2>/dev/null
        rm logs/mcp_server.pid
    fi
    if [ -f logs/api_server.pid ]; then
        kill $(cat logs/api_server.pid) 2>/dev/null
        rm logs/api_server.pid
    fi
    echo "已停止所有服务，再见！"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 启动 MCP Server
echo "[3/4] 启动 MCP Server..."
python3 -m mcp_server.server > logs/mcp_server.log 2>&1 &
echo $! > logs/mcp_server.pid
sleep 3

# 启动 API Server
echo "[4/4] 启动 API Server..."
uvicorn api.app:app --host 0.0.0.0 --port 8000 > logs/api_server.log 2>&1 &
echo $! > logs/api_server.pid
sleep 2

# 打开浏览器
echo ""
echo "========================================"
echo " ✓ 系统已启动！正在打开浏览器..."
echo " 访问地址：http://localhost:8000"
echo " 按 Ctrl+C 停止所有服务"
echo "========================================"
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:8000
else
    xdg-open http://localhost:8000 2>/dev/null || true
fi

# 保持前台运行
wait
