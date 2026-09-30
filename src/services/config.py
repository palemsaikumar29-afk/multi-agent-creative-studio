"""Environment-only configuration. No secrets, keys, or model names hardcoded."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class Settings:
    llm_provider: str = _env("LLM_PROVIDER", "groq").lower()
    openai_api_key: str = _env("OPENAI_API_KEY")
    openai_model: str = _env("OPENAI_MODEL", "gpt-4o-mini")
    gemini_api_key: str = _env("GEMINI_API_KEY")
    gemini_model: str = _env("GEMINI_MODEL", "gemini-2.0-flash")
    groq_api_key: str = _env("GROQ_API_KEY")
    groq_model: str = _env("GROQ_MODEL", "openai/gpt-oss-20b")
    llm_max_attempts: int = int(_env("LLM_MAX_ATTEMPTS", "3") or 3)
    llm_backoff_base: float = float(_env("LLM_BACKOFF_BASE", "1.0") or 1.0)
    openai_timeout: float = 60.0
    gemini_timeout: float = 60.0
    groq_timeout: float = 60.0
    store_db_path: str = _env("STORE_DB_PATH", "data/musicstore.db")
    image_provider: str = _env("IMAGE_PROVIDER", "auto").lower()
    openai_image_model: str = _env("OPENAI_IMAGE_MODEL", "dall-e-3")
    pollinations_model: str = _env("POLLINATIONS_MODEL", "flux")
    studio_output_dir: str = _env("STUDIO_OUTPUT_DIR", "outputs")


settings = Settings()
