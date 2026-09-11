import json
import logging
from typing import Dict, Any, Optional
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)


def get_groq_client() -> Optional[Groq]:
    if not settings.groq_api_key or settings.groq_api_key.startswith("gsk_placeholder"):
        return None
    try:
        return Groq(api_key=settings.groq_api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize Groq client: {e}")
        return None


def call_groq_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> Dict[str, Any]:
    """Execute Groq LLM inference expecting a structured JSON response."""
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
        return json.loads(content)
    except Exception as e:
        logger.error(f"Groq API call error: {e}")
        raise e
