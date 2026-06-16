import inspect
import os
from typing import Annotated, Any

from dotenv import load_dotenv
from pydantic import Field
from mcp.server.fastmcp import FastMCP

from runtime.skills import load_all_skills, run_skill_by_definition

load_dotenv()

mcp = FastMCP("SkillServer")


def _json_schema_to_python_type(prop_schema: dict) -> Any:
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
    return str


def make_tool_handler(skill):
    async def handler(**kwargs) -> str:
        return await run_skill_by_definition(skill, kwargs)

    schema = skill.input_schema or {}
    properties = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])

    parameters = []
    for name, prop_schema in properties.items():
        py_type = _json_schema_to_python_type(prop_schema)
        annotation = Annotated[
            py_type,
            Field(description=prop_schema.get("description", "") or ""),
        ]
        if name in required:
            param = inspect.Parameter(
                name=name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
            )
        else:
            param = inspect.Parameter(
                name=name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
                default=prop_schema.get("default", None),
            )
        parameters.append(param)

    handler.__signature__ = inspect.Signature(
        parameters=parameters,
        return_annotation=str,
    )
    return handler


def register_skills():
    for skill in load_all_skills():
        handler = make_tool_handler(skill)
        handler.__name__ = skill.name
        handler.__doc__ = skill.description
        mcp.tool(name=skill.name, description=skill.description)(handler)


register_skills()


if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8001"))
    mcp.settings.port = port
    mcp.run(transport="sse")

