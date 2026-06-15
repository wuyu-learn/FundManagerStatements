import os
from typing import Optional


_OUTER_QUOTES = "\"'“”‘’"


def clean_env_value(value: Optional[str], default: str = "") -> str:
    if value is None:
        return default
    return value.strip().strip(_OUTER_QUOTES).strip()


def get_llm_settings() -> dict:
    return {
        "api_key": clean_env_value(os.getenv("OPENAI_API_KEY")),
        "base_url": clean_env_value(
            os.getenv("OPENAI_BASE_URL"),
            "https://api.openai.com/v1",
        ),
        "model": clean_env_value(os.getenv("LLM_MODEL"), "gpt-4o"),
    }
