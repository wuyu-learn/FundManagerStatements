import json

from jinja2 import Template

from runtime.llm import get_async_openai_client, get_model_name
from .definitions import SkillDefinition
from .loader import load_all_skills


FALLBACK_PROMPT = """
你是一个 AI 助手。当前 Skill 的 Prompt 尚未配置，请根据以下输入生成合理的 mock 响应。
输入参数：{{ input_json }}
请直接返回 JSON 格式结果，不要有任何额外说明。
"""


def is_empty_template(template_str: str) -> bool:
    stripped = template_str.strip()
    return not stripped or stripped.startswith("<!--")


async def call_llm_json(prompt: str) -> dict:
    response = await get_async_openai_client().chat.completions.create(
        model=get_model_name(),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


async def run_skill_by_definition(skill: SkillDefinition, inputs: dict) -> str:
    """Render a markdown skill and return the LLM result as a JSON string."""
    template_str = skill.prompt_template
    if is_empty_template(template_str):
        rendered = Template(FALLBACK_PROMPT).render(
            input_json=json.dumps(inputs, ensure_ascii=False)
        )
    else:
        rendered = Template(template_str).render(**inputs)
    result = await call_llm_json(rendered)
    return json.dumps(result, ensure_ascii=False)


async def run_skill(skill_name: str, inputs: dict) -> str:
    skill = next((s for s in load_all_skills() if s.name == skill_name), None)
    if skill is None:
        raise ValueError(f"Skill not found: {skill_name}")
    return await run_skill_by_definition(skill, inputs)

