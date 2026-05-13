import logging, asyncio
from functools import wraps
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import AsyncOpenAI
from config import OPENAI_BASE_URL, OPENAI_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

FALLBACK_TEXT = "Сервер мыслей перегружен. Попробуйте позже."


def async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0, fallback_value=None):
    """Асинхронный декоратор с экспоненциальной задержкой и fallback."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")
                    if attempt < max_attempts:
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, max_delay)
            logger.error(f"All {max_attempts} attempts failed. Using fallback.")
            return fallback_value
        return wrapper
    return decorator


class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)

    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0, fallback_value=None)
    async def stream_completion(self, messages, max_tokens=4096, temperature=0.5):
        """Асинхронный генератор, возвращающий чанки текста."""
        try:
            response = await self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
        except Exception as e:
            logger.error(f"Stream completion error: {e}")
            yield FALLBACK_TEXT

    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0, fallback_value=FALLBACK_TEXT)
    async def completion(self, messages, max_tokens=4096, temperature=0.5, json_mode=False):
        """Обычный не-стриминговый запрос. Поддерживает JSON mode для structured outputs."""
        try:
            kwargs = {
                "model": LLM_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Completion error: {e}")
            return FALLBACK_TEXT

    async def json_completion(self, messages, max_tokens=4096, temperature=0.3):
        """Запрос с гарантированным JSON ответом через response_format."""
        return await self.completion(messages, max_tokens=max_tokens, temperature=temperature, json_mode=True)