"""LiteLLM -> OpenRouter -> Cerebras client with structured output."""

import logging
import os

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")  # skip network fetch on import

from litellm import completion  # noqa: E402

from .mock import mock_response
from .models import LLMResponse
from .prompt import build_messages

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
FALLBACK_MESSAGE = "Sorry, I could not process that request."


def _is_mock() -> bool:
    """True when LLM_MOCK=true in the environment."""
    return os.getenv("LLM_MOCK", "false").strip().lower() == "true"


def get_llm_response(context: dict, history: list[dict], user_message: str) -> LLMResponse:
    """Return the assistant's structured response; never raises (falls back on any error)."""
    if _is_mock():
        return mock_response(user_message)
    messages = build_messages(context, history, user_message)
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=LLMResponse,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
        return LLMResponse.model_validate_json(response.choices[0].message.content)
    except Exception:
        logger.exception("LLM call or parsing failed")
        return LLMResponse(message=FALLBACK_MESSAGE)
