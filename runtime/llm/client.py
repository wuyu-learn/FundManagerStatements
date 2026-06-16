from __future__ import annotations

from dotenv import load_dotenv
from openai import AsyncOpenAI

from config import get_llm_settings

load_dotenv()

_CLIENT: AsyncOpenAI | None = None


def get_model_name() -> str:
    return get_llm_settings()["model"]


def get_async_openai_client() -> AsyncOpenAI:
    global _CLIENT
    if _CLIENT is None:
        settings = get_llm_settings()
        _CLIENT = AsyncOpenAI(
            api_key=settings["api_key"],
            base_url=settings["base_url"],
        )
    return _CLIENT
