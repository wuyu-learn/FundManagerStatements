from dataclasses import dataclass


@dataclass
class SkillDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    prompt_template: str

