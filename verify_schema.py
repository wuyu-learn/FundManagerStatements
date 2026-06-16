"""Quick check: import the FastMCP server (which triggers register_skills())
and dump the JSON schema FastMCP is exposing for each registered tool.

Exits 0 iff every required property from the skill's input_schema survives the
round-trip as an independent, correctly-typed, required field in the tool's
inputSchema. This is the regression test for the **kwargs flattening bug.
"""

import json
import sys

# Importing the module triggers `register_skills()` which registers tools on mcp.
import runtime.mcp.server as server


def _list_registered_tools():
    """Reach into FastMCP's internal tool manager.

    FastMCP doesn't expose a public tool-listing API on the high-level object,
    so we go through the private ToolManager._tools dict (stable across the
    version range we care about). Each Tool exposes ``parameters`` as a
    pre-rendered JSON schema dict — that's exactly the schema the LLM sees,
    so we don't need to call model_json_schema() ourselves.
    """
    tool_manager = server.mcp._tool_manager
    tools = []
    for name, tool in tool_manager._tools.items():
        schema = tool.parameters
        if hasattr(schema, "model_json_schema"):
            schema = schema.model_json_schema()
        tools.append((name, schema))
    return tools


def main() -> int:
    failures = []
    skills = {s.name: s for s in server.load_all_skills()}

    for tool_name, schema in _list_registered_tools():
        print(f"\n=== Tool: {tool_name} ===")
        print(json.dumps(schema, ensure_ascii=False, indent=2))

        skill = skills.get(tool_name)
        if skill is None:
            failures.append(f"[{tool_name}] no matching skill loaded")
            continue

        expected_props = (skill.input_schema or {}).get("properties", {}) or {}
        expected_required = set((skill.input_schema or {}).get("required", []) or [])

        actual_props = schema.get("properties", {}) or {}
        actual_required = set(schema.get("required", []) or [])

        # The bug: a single 'kwargs' string field swallowing the whole payload.
        if "kwargs" in actual_props:
            failures.append(
                f"[{tool_name}] schema is still flattened to a single 'kwargs' "
                f"string field — **kwargs flattening bug is NOT fixed"
            )

        for prop_name, prop_schema in expected_props.items():
            if prop_name not in actual_props:
                failures.append(
                    f"[{tool_name}] missing property '{prop_name}' in schema"
                )
                continue
            actual_type = actual_props[prop_name].get("type")
            expected_type = prop_schema.get("type", "string")
            if actual_type != expected_type:
                failures.append(
                    f"[{tool_name}] property '{prop_name}' has type "
                    f"{actual_type!r}, expected {expected_type!r}"
                )

        for prop_name in expected_required:
            if prop_name not in actual_required:
                failures.append(
                    f"[{tool_name}] required property '{prop_name}' is NOT "
                    f"marked required in the exposed schema"
                )

    print("\n=== Summary ===")
    if failures:
        print("FAIL — schema mismatch:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — every required property from skill.input_schema is exposed "
          "as an independent, correctly-typed, required field.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
