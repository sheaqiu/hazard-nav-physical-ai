"""Configuration for the OpenAI-compatible language and audio gateway."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class AISettings:
    provider: str
    api_key: str
    planner_model: str
    transcription_model: str
    base_url: str | None = None
    default_headers: dict[str, str] | None = None
    request_extra_body: dict[str, object] | None = None


def load_ai_settings(source: Mapping[str, str] | None = None) -> AISettings:
    """Load one explicit provider configuration from environment variables."""
    env = environ if source is None else source
    openrouter_key = env.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        headers = {
            "HTTP-Referer": env.get(
                "OPENROUTER_HTTP_REFERER", "http://localhost:6080"
            ),
            "X-Title": env.get("OPENROUTER_APP_NAME", "HazardNav"),
        }
        return AISettings(
            provider="openrouter",
            api_key=openrouter_key,
            base_url=env.get("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
            planner_model=env.get("OPENROUTER_MODEL", "openrouter/free"),
            transcription_model=env.get(
                "OPENROUTER_TRANSCRIBE_MODEL",
                "openai/whisper-large-v3-turbo",
            ),
            default_headers=headers,
            request_extra_body={"provider": {"require_parameters": True}},
        )

    openai_key = env.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        return AISettings(
            provider="openai",
            api_key=openai_key,
            planner_model=env.get("OPENAI_MODEL", "gpt-6-astra"),
            transcription_model=env.get(
                "OPENAI_TRANSCRIBE_MODEL", "gpt-transcribe"
            ),
        )

    raise RuntimeError(
        "set OPENROUTER_API_KEY (recommended) or OPENAI_API_KEY"
    )


def create_ai_client(settings: AISettings):
    """Construct the SDK client lazily so pure configuration tests need no SDK."""
    from openai import OpenAI

    arguments: dict[str, object] = {"api_key": settings.api_key}
    if settings.base_url:
        arguments["base_url"] = settings.base_url
    if settings.default_headers:
        arguments["default_headers"] = settings.default_headers
    return OpenAI(**arguments)
