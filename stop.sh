#!/bin/bash
echo "正在停止 AI Demo System..."
if [ -f logs/mcp_server.pid ]; then
    kill $(cat logs/mcp_server.pid) 2>/dev/null
    rm logs/mcp_server.pid
    echo "MCP Server 已停止"
fi
if [ -f logs/api_server.pid ]; then
    kill $(cat logs/api_server.pid) 2>/dev/null
    rm logs/api_server.pid
    echo "API Server 已停止"
fi
echo "完成。"
