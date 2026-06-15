import os
import json
from dotenv import load_dotenv
load_dotenv()

from jinja2 import Template
from openai import AsyncOpenAI
from mcp.server.fastmcp import FastMCP
from .skill_loader import load_all_skills

mcp = FastMCP("SkillServer")

openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

FALLBACK_PROMPT = """
你是一个 AI 助手。当前 Skill 的 Prompt 尚未配置，请根据以下输入生成合理的 mock 响应。
输入参数：{{ input_json }}
请直接返回 JSON 格式结果，不要有任何额外说明。
"""


async def call_llm(prompt: str) -> dict:
    response = await openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def is_empty_template(template_str: str) -> bool:
    stripped = template_str.strip()
    return not stripped or stripped.startswith("<!--")


def make_tool_handler(skill):
    async def handler(**kwargs) -> str:
        template_str = skill.prompt_template
        if is_empty_template(template_str):
            rendered = Template(FALLBACK_PROMPT).render(
                input_json=json.dumps(kwargs, ensure_ascii=False)
            )
        else:
            rendered = Template(template_str).render(**kwargs)
        result = await call_llm(rendered)
        return json.dumps(result, ensure_ascii=False)
    return handler


def register_skills():
    skills = load_all_skills()
    for skill in skills:
        handler = make_tool_handler(skill)
        handler.__name__ = skill.name
        handler.__doc__ = skill.description
        mcp.tool(name=skill.name, description=skill.description)(handler)


register_skills()


if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8001"))
    mcp.run(transport="sse", port=port)
