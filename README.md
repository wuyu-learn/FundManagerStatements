# AI Demo System

## 环境要求
- Python 3.11 或以上
- 能访问 OpenAI API（或兼容接口）

## 首次启动

### Windows
1. 双击运行 `start.bat`
2. 首次运行会自动创建 `.env` 文件并打开记事本
3. 填写 `OPENAI_API_KEY`，保存后重新双击 `start.bat`
4. 等待依赖安装完成，浏览器自动打开

### Mac / Linux
1. 终端进入项目目录
2. 首次赋予执行权限：`chmod +x start.sh stop.sh`
3. 运行：`./start.sh`
4. 首次运行会提示编辑 `.env` 文件，填写 `OPENAI_API_KEY` 后重新运行
5. 等待依赖安装完成，浏览器自动打开

## 停止服务
- Windows：双击 `stop.bat` 或在 `start.bat` 窗口按任意键
- Mac/Linux：在终端按 `Ctrl+C`，或运行 `./stop.sh`

## 新增 Skill
在 `skills/` 目录参照 `example_skill.md` 格式新建 `.md` 文件，
填写 YAML Front Matter 元信息和 Prompt 正文，重启服务即可自动注册。

## 日志查看
- MCP Server 日志：`logs/mcp_server.log`
- API Server 日志：`logs/api_server.log`
