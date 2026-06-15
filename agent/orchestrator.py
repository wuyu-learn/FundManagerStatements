import os
import json
from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client
from .event_stream import EventEmitter, EventType

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

REACT_SYSTEM_PROMPT = """
你是一个智能分析 Agent，可以调用以下 Skill 工具完成用户的分析任务：

{tools_description}

## 工作规则
每次只返回一个 JSON 对象，格式如下：

调用工具时：
{{
  "thought": "我的思考过程",
  "action": "tool_name",
  "action_input": {{"param1": "value1"}}
}}

任务完成时：
{{
  "thought": "已完成所有分析",
  "action": "final_answer",
  "action_input": {{"answer": "完整的中文分析报告"}}
}}

注意：每次只返回一个 JSON，不要有额外文字；合理规划调用顺序，充分利用上一步结果。
"""


class AgentOrchestrator:
    def __init__(self, emitter: EventEmitter):
        self.emitter = emitter

    async def run(self, user_input: str):
        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tools = tools_result.tools
                tools_description = "\n".join(
                    [f"- **{t.name}**: {t.description}" for t in tools]
                )

                messages = [
                    {"role": "system", "content": REACT_SYSTEM_PROMPT.format(
                        tools_description=tools_description
                    )},
                    {"role": "user", "content": user_input},
                ]

                for iteration in range(10):
                    response = await openai_client.chat.completions.create(
                        model=LLM_MODEL,
                        messages=messages,
                        response_format={"type": "json_object"},
                    )
                    raw = response.choices[0].message.content

                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        await self.emitter.emit(EventType.ERROR, {
                            "message": "LLM 返回格式错误", "raw": raw
                        })
                        break

                    thought = parsed.get("thought", "")
                    action = parsed.get("action", "")
                    action_input = parsed.get("action_input", {})

                    await self.emitter.emit(EventType.THOUGHT, {
                        "content": thought,
                        "iteration": iteration + 1
                    })

                    if action == "final_answer":
                        await self.emitter.emit(EventType.FINAL_ANSWER, {
                            "content": action_input.get("answer", "")
                        })
                        break

                    await self.emitter.emit(EventType.ACTION, {
                        "tool": action,
                        "input": action_input,
                        "iteration": iteration + 1
                    })
                    await self.emitter.emit(EventType.SKILL_START, {"skill": action})

                    try:
                        result = await session.call_tool(action, action_input)
                        observation = result.content[0].text if result.content else "{}"
                    except Exception as e:
                        observation = json.dumps({"error": str(e)})
                        await self.emitter.emit(EventType.ERROR, {
                            "message": f"Tool 调用失败: {e}"
                        })

                    await self.emitter.emit(EventType.SKILL_END, {
                        "skill": action,
                        "output_preview": observation[:300]
                    })
                    await self.emitter.emit(EventType.OBSERVATION, {
                        "tool": action,
                        "content": observation,
                        "iteration": iteration + 1
                    })

                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": f"Observation: {observation}"})

                else:
                    await self.emitter.emit(EventType.ERROR, {"message": "已达到最大迭代次数"})

                await self.emitter.emit(EventType.FINAL_ANSWER, {"content": "__DONE__"})
