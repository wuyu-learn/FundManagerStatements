import os
import frontmatter
from dataclasses import dataclass

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")


@dataclass
class SkillDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    prompt_template: str


def load_all_skills() -> list[SkillDefinition]:
    skills = []
    skills_path = os.path.abspath(SKILLS_DIR)
    for filename in os.listdir(skills_path):
        if filename.endswith(".md"):
            filepath = os.path.join(skills_path, filename)
            post = frontmatter.load(filepath)
            skill = SkillDefinition(
                name=post.metadata["name"],
                description=post.metadata["description"],
                input_schema=post.metadata.get("input_schema", {}),
                output_schema=post.metadata.get("output_schema", {}),
                prompt_template=post.content,
            )
            skills.append(skill)
    return skills
