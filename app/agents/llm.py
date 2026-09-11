import json
import logging
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, ValidationError
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)


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
        logger.error(f"Groq API communication error: {e}")
        raise e
