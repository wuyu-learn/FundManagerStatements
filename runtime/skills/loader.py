import os

import yaml

from .definitions import SkillDefinition

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKILLS_DIR = os.path.join(ROOT_DIR, "skills")


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

