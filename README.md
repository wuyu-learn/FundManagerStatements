# AI Demo System

## 架构说明

默认运行链路：

```
App API → Agent → runtime/skills → skills/Review.md → LLM
```

MCP Server 仍然保留，但默认不启动。需要把 Skill 作为标准 MCP tool 暴露给外部客户端时，
在 `.env` 中设置：

```
ENABLE_MCP_SERVER=true
```

开启后可选链路为：

```
外部 MCP Client → runtime/mcp → runtime/skills → skills/Review.md → LLM
```

## 环境要求
- 默认审核链路：Python 3.9 或以上
- 可选 MCP Server：Python 3.11 或以上
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
在 `skills/` 目录新建 `.md` 文件，文件必须包含 YAML Front Matter 和 Prompt 正文。
Front Matter 至少包含：

```yaml
---
name: Example
description: 简短说明这个 Skill 的用途、输入要求和输出目标
input_schema:
  type: object
  properties: {}
output_schema:
  type: object
  properties: {}
---
```

当前项目的 Skill 是项目内自定义格式：`runtime/skills/loader.py` 会读取 `skills/*.md`，
并把 `name`、`description`、`input_schema`、`output_schema` 和正文 Prompt 注册为可执行工具。
如果开启 MCP Server，这些 Skill 还会按 `input_schema` 暴露为 MCP tool。

仓库里也保留了标准技能包目录形态的 Skill 示例：`skills/fund-review/SKILL.md`。
它用于沉淀可复用的技能说明、文本切分脚本、详细规则和确定性校验脚本；当前 API 链路仍以
`skills/Review.md` 作为运行入口。

分层约定：
- `app/` 负责 HTTP API、用户会话和前端页面入口。
- `agent/` 负责意图识别、计划编排、事件流和执行轨迹。
- `runtime/llm/` 负责模型客户端。
- `runtime/skills/` 负责 Skill 定义、发现、执行和技能包资源加载。
- `runtime/mcp/` 负责把 Skill 暴露为可选 MCP tool。
- `runtime/storage/` 负责运行期缓存，例如 `data/raw_docs`。
- `skills/fund-review/` 负责基金评述审核相关能力，包括切句编号、审核规则和输出校验。

## 日志查看
- MCP Server 日志：`logs/mcp_server.log`（仅 `ENABLE_MCP_SERVER=true` 时生成）
- API Server 日志：`logs/api_server.log`
