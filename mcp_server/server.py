import os
import json
import inspect
from typing import Annotated, Any
from dotenv import load_dotenv
load_dotenv()

from jinja2 import Template
from openai import AsyncOpenAI
from pydantic import Field
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


def _json_schema_to_python_type(prop_schema: dict) -> Any:
    """Best-effort mapping from JSON Schema property to a Python annotation.

    FastMCP's func_metadata introspects ``inspect.signature``; if the handler
    takes ``**kwargs`` it flattens everything into a single string field and the
    LLM is then asked to put structured data into a flat string. So we build a
    real signature from ``skill.input_schema`` and let pydantic emit a proper
    JSON schema with named, typed properties.
    """
    json_type = prop_schema.get("type", "string")
    if json_type == "string":
        return str
    if json_type == "integer":
        return int
    if json_type == "number":
        return float
    if json_type == "boolean":
        return bool
    if json_type == "array":
        return list
    if json_type == "object":
        return dict
    # Fallback: stay permissive so a missing type never blows up schema emission.
    return str


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

    # Build a real signature from skill.input_schema so FastMCP exposes each
    # property as an independent, correctly-typed, required-or-optional field
    # instead of collapsing the whole payload into one ``kwargs`` string.
    schema = skill.input_schema or {}
    properties = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])

    parameters = []
    for name, prop_schema in properties.items():
        py_type = _json_schema_to_python_type(prop_schema)
        annotation = Annotated[py_type, Field(description=prop_schema.get("description", "") or "")]
        if name in required:
            param = inspect.Parameter(
                name=name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
            )
        else:
            default = prop_schema.get("default", None)
            param = inspect.Parameter(
                name=name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
                default=default,
            )
        parameters.append(param)

    handler.__signature__ = inspect.Signature(
        parameters=parameters,
        return_annotation=str,
    )
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
    mcp.settings.port = port
    mcp.run(transport="sse")
