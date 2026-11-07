'''Documentation String'''
from openai import OpenAI
from functools import lru_cache
from ..settings import get_settings
from .augment import SYSTEM_PROMPT
import logging

logger = logging.getLogger(__name__)

class GenerationError(RuntimeError):
    '''LLM Generation Error Response Class'''


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    settings = get_settings()

    return OpenAI(
        base_url = settings.llm_base_url,
        api_key = settings.llm_api_key,
        timeout = settings.llm_timeout_seconds,
        max_retries = 2
    )


def generate_answer(augmented_prompt:str) -> str:
    settings = get_settings()

    try:
        generated = _get_client().chat.completions.create( #generated or completions either name you use
            model =  settings.llm_model,
            max_tokens = settings.llm_max_tokens,
            messages = [
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":augmented_prompt}
            ]
        )
    except Exception as err:
        logger.exception("LLM Call Failed")

        raise GenerationError(err.__class__.__name__) from exec

    return generated.choices[0].message.content or ""
