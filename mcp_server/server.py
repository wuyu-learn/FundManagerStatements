import os
import inspect
from typing import Annotated, Any
from dotenv import load_dotenv
load_dotenv()

from pydantic import Field
from mcp.server.fastmcp import FastMCP
from .skill_loader import load_all_skills
from skill_runtime import run_skill_by_definition

mcp = FastMCP("SkillServer")


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
        return await run_skill_by_definition(skill, kwargs)

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
