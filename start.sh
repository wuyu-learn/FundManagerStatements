#!/bin/bash
set -e

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

set -a
source .env
set +a

API_PORT="${API_PORT:-8000}"
ENABLE_MCP_SERVER="${ENABLE_MCP_SERVER:-false}"

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_OK=$(python3 -c 'import sys; print("1" if sys.version_info >= (3, 9) else "0")')
if [ "$PY_OK" != "1" ]; then
    echo "[错误] 当前 python3 版本是 $PY_VERSION，项目默认链路需要 Python 3.9+"
    exit 1
fi
if [ "$ENABLE_MCP_SERVER" = "true" ]; then
    MCP_PY_OK=$(python3 -c 'import sys; print("1" if sys.version_info >= (3, 11) else "0")')
    if [ "$MCP_PY_OK" != "1" ]; then
        echo "[错误] 启用 MCP Server 需要 Python 3.11+，当前是 $PY_VERSION"
        echo "请先关闭 ENABLE_MCP_SERVER，或安装 Python 3.11+ 后重建 .venv。"
        exit 1
    fi
fi

# 创建日志目录
mkdir -p logs

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv .venv
else
    VENV_OK=$(.venv/bin/python -c 'import sys; print("1" if sys.version_info >= (3, 9) else "0")')
    VENV_VERSION=$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [ "$VENV_OK" != "1" ]; then
        echo "[错误] 当前 .venv 使用 Python $VENV_VERSION，项目默认链路需要 Python 3.9+"
        echo "请删除旧虚拟环境后重新运行：rm -rf .venv && ./start.sh"
        exit 1
    fi
    if [ "$ENABLE_MCP_SERVER" = "true" ]; then
        VENV_MCP_OK=$(.venv/bin/python -c 'import sys; print("1" if sys.version_info >= (3, 11) else "0")')
        if [ "$VENV_MCP_OK" != "1" ]; then
            echo "[错误] 当前 .venv 使用 Python $VENV_VERSION，启用 MCP Server 需要 Python 3.11+"
            echo "请关闭 ENABLE_MCP_SERVER，或删除 .venv 后用 Python 3.11+ 重建。"
            exit 1
        fi
    fi
fi

# 激活并安装依赖
echo "[2/4] 安装依赖（首次运行需要几分钟）..."
source .venv/bin/activate
pip install -r requirements.txt -q
if [ "$ENABLE_MCP_SERVER" = "true" ]; then
    pip install -r requirements-mcp.txt -q
fi

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

if [ "$ENABLE_MCP_SERVER" = "true" ]; then
    echo "[3/4] 启动 MCP Server（可选外部工具入口）..."
    python3 -m mcp_server.server > logs/mcp_server.log 2>&1 &
    echo $! > logs/mcp_server.pid
    sleep 3
else
    echo "[3/4] 跳过 MCP Server（Agent 默认直接调用 Skill）"
fi

# 启动 API Server
echo "[4/4] 启动 API Server..."
uvicorn api.app:app --host 127.0.0.1 --port "$API_PORT" > logs/api_server.log 2>&1 &
echo $! > logs/api_server.pid
sleep 2

# 打开浏览器
echo ""
echo "========================================"
echo " ✓ 系统已启动！正在打开浏览器..."
echo " 访问地址：http://localhost:$API_PORT"
echo " 按 Ctrl+C 停止所有服务"
echo "========================================"
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:$API_PORT"
else
    xdg-open "http://localhost:$API_PORT" 2>/dev/null || true
fi

# 保持前台运行
wait
