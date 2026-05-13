import logging
from openai import AsyncOpenAI
from config import OPENAI_BASE_URL, OPENAI_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)

    async def stream_completion(self, messages, max_tokens=4096, temperature=0.5):
        """Асинхронный генератор, возвращающий чанки текста."""
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

    async def completion(self, messages, max_tokens=4096, temperature=0.5):
        """Обычный не-стриминговый запрос."""
        response = await self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content