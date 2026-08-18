from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from config import get_settings


def get_chat_model() -> BaseChatModel | None:
    settings = get_settings()
    if not settings.llm_api_key:
        return None
    if settings.llm_provider not in {"openai", "openai_compatible", "deepseek", "qwen"}:
        raise ValueError(f"当前未配置 Provider 适配器: {settings.llm_provider}")
    kwargs = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "temperature": settings.llm_temperature,
        "timeout": settings.llm_timeout,
        "max_retries": 1,
    }
    base_url = settings.llm_base_url
    if settings.llm_provider == "deepseek" and not base_url:
        base_url = "https://api.deepseek.com"
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
