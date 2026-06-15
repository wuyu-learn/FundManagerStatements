import os
from dataclasses import dataclass
import yaml

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")


@dataclass
class SkillDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    prompt_template: str


def load_skill_file(filepath: str) -> tuple[dict, str]:
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    if not raw.startswith("---"):
        return {}, raw

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw

    metadata = yaml.safe_load(parts[1]) or {}
    content = parts[2].lstrip("\n")
    return metadata, content


def load_all_skills() -> list[SkillDefinition]:
    skills = []
    skills_path = os.path.abspath(SKILLS_DIR)
    for filename in os.listdir(skills_path):
        if filename.endswith(".md"):
            filepath = os.path.join(skills_path, filename)
            metadata, content = load_skill_file(filepath)
            skill = SkillDefinition(
                name=metadata["name"],
                description=metadata["description"],
                input_schema=metadata.get("input_schema", {}),
                output_schema=metadata.get("output_schema", {}),
                prompt_template=content,
            )
            skills.append(skill)
    return skills
