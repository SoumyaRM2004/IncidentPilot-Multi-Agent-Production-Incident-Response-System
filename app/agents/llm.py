import json
import logging
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, ValidationError
from groq import Groq, RateLimitError
from app.config import settings

logger = logging.getLogger(__name__)


class LLMRateLimitError(Exception):
    """Raised when Groq API encounters an HTTP 429 rate limit or token exhaustion."""
    def __init__(self, message: str = "LLM rate limit reached (HTTP 429)."):
        super().__init__(message)
        self.message = message


_rate_limit_active: bool = False
_rate_limit_reason: Optional[str] = None


def is_rate_limited() -> bool:
    """Check if the Groq LLM API is currently rate-limited."""
    return _rate_limit_active


def get_rate_limit_reason() -> Optional[str]:
    """Retrieve the concise recorded rate-limit reason if active."""
    return _rate_limit_reason


def set_rate_limited(reason: str) -> None:
    """Mark the LLM API as rate-limited with a specific diagnostic reason."""
    global _rate_limit_active, _rate_limit_reason
    _rate_limit_active = True
    _rate_limit_reason = reason


def reset_rate_limit_state() -> None:
    """Reset the LLM rate limit state (primarily for test isolation)."""
    global _rate_limit_active, _rate_limit_reason
    _rate_limit_active = False
    _rate_limit_reason = None


def is_rate_limit_error(e: Exception) -> bool:
    """Check whether an exception represents an HTTP 429 or token exhaustion error."""
    if isinstance(e, (RateLimitError, LLMRateLimitError)):
        return True
    status = getattr(e, "status_code", None)
    if status == 429:
        return True
    msg = str(e).lower()
    return "429" in msg or "rate limit" in msg or "rate_limit" in msg or "tpd limit" in msg or "tokens per day" in msg


def get_groq_client() -> Optional[Groq]:
    """Instantiate Groq client if valid API key is present."""
    if not settings.groq_api_key or settings.groq_api_key.startswith("gsk_placeholder"):
        return None
    try:
        return Groq(api_key=settings.groq_api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize Groq client: {e}")
        return None


def call_groq_json(
    system_prompt: str,
    user_prompt: str,
    schema_model: Optional[Type[BaseModel]] = None,
    temperature: float = 0.1
) -> Dict[str, Any]:
    """Execute Groq LLM inference expecting a structured JSON response with optional Pydantic validation."""
    if is_rate_limited():
        raise LLMRateLimitError(get_rate_limit_reason() or "LLM rate limit active (TPD/RPM exhausted).")

    client = get_groq_client()
    if not client:
        raise ValueError("GROQ_API_KEY is not configured or invalid in environment.")

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": f"{system_prompt}\nYou MUST respond with valid JSON only."},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)

        if schema_model:
            # Validate through Pydantic schema
            validated = schema_model.model_validate(parsed)
            return validated.model_dump()

        return parsed
    except ValidationError as ve:
        logger.error(f"Groq output failed Pydantic schema validation: {ve}")
        raise ValueError(f"LLM returned malformed schema: {ve}") from ve
    except Exception as e:
        if is_rate_limit_error(e):
            err_msg = getattr(e, "message", str(e))
            concise_reason = f"Rate limit reached (HTTP 429): {err_msg}"
            set_rate_limited(concise_reason)
            logger.warning(f"Groq API rate limit detected: {concise_reason}")
            raise LLMRateLimitError(concise_reason) from e
        logger.error(f"Groq API communication error: {e}")
        raise e
