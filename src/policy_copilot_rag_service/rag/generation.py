"""Generate grounded Gemini answers within the interactive request budget."""
import logging
import math
from time import monotonic
from functools import lru_cache

import httpx
import httpx2
from google import genai
from google.genai import errors, types
from ..settings import get_settings
from .augment import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class GenerationError(RuntimeError):
    """Provider failure with a safe message for the API response."""
    detail = "The LLM is currently unavailable. Please try again."

    def __init__(self, reason: str, *, detail: str | None = None):
        super().__init__(reason)
        if detail is not None:
            self.detail = detail


class GenerationTimeout(GenerationError):
    """The provider did not respond within the configured timeout."""
    detail = "The LLM request timed out. Please try again."

@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(
        api_key=settings.llm_api_key,
        http_options=types.HttpOptions(
            # The SDK expects milliseconds. Keep one attempt so retries cannot
            # multiply the timeout beyond the frontend proxy's request budget.
            timeout=max(1,math.ceil(settings.llm_timeout_seconds * 1000)),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def generate_answer(augmented_prompt:str) -> str:
    settings = get_settings()
    started = monotonic()

    try:
        generated = _get_client().models.generate_content(
            model = settings.llm_model,
            contents = augmented_prompt,
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=settings.llm_max_tokens
            )
        )
        text = generated.text
    except (TimeoutError,httpx.TimeoutException,httpx2.TimeoutException) as err:
        logger.warning("LLM request timed out (model=%s, elapsed=%.2fs)",
                       settings.llm_model,monotonic()-started)
        raise GenerationTimeout(err.__class__.__name__) from err
    except errors.APIError as err:
        logger.exception("LLM provider rejected request (model=%s, status=%s, elapsed=%.2fs)",
                         settings.llm_model,err.code,monotonic()-started)
        if err.code in (408,504):
            raise GenerationTimeout(err.__class__.__name__) from err
        if err.code == 429:
            raise GenerationError(err.__class__.__name__,detail=
                "The LLM provider's quota or rate limit was reached. Please try again later.") from err
        if err.code in (400,401,403,404):
            raise GenerationError(err.__class__.__name__,detail=
                "The LLM provider rejected its configuration. Check the API key and model.") from err
        raise GenerationError(err.__class__.__name__) from err
    except Exception as err:
        logger.exception("LLM call failed (model=%s, elapsed=%.2fs)",
                         settings.llm_model,monotonic()-started)
        raise GenerationError(err.__class__.__name__) from err

    if not text or not text.strip():
        logger.warning("LLM returned no answer (model=%s, elapsed=%.2fs)",
                       settings.llm_model,monotonic()-started)
        raise GenerationError("Empty response",detail=
            "The LLM returned no answer. Please try again or rephrase your question.")

    logger.info("LLM answer generated (model=%s, elapsed=%.2fs)",
                settings.llm_model,monotonic()-started)
    return text
