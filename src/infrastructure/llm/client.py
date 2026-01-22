"""Клиент для взаимодействия с LLM.

Инкапсулирует операции с языковой моделью через OpenAI-совместимый API.
Реализует generic интерфейс LLMPort (dumb adapter).
"""

import logging
import time

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel

from src.config.metrics import get_metrics_collector
from src.config.settings import settings
from src.config.telemetry import traced_operation

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент для работы с LLM через OpenAI-совместимый API.

    Предоставляет базовые методы генерации (generate, generate_structured).
    Не содержит бизнес-логики (промптов) приложения.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        """Инициализирует LLM-клиент.

        Args:
            api_key: API ключ.
            base_url: Base URL API.
            model: Имя основной модели.
            http_client: Опциональный httpx клиент.
            client: Готовый AsyncOpenAI клиент.

        """
        if client is not None:
            self.client = client
            self._http_client = None
            logger.info("Using injected AsyncOpenAI client")
        else:
            self._http_client = http_client or httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=200,
                    max_keepalive_connections=50,
                ),
                timeout=httpx.Timeout(timeout=settings.llm_timeout),
            )

            final_api_key = api_key or settings.openrouter_api_key.get_secret_value()
            final_base_url = base_url or settings.openrouter_base_url

            self.client = AsyncOpenAI(
                api_key=final_api_key,
                base_url=final_base_url,
                http_client=self._http_client,
            )
            logger.info(
                "Created LLMClient (model=%s, base_url=%s)",
                model or settings.models.main,
                final_base_url,
            )

        self.model = model or settings.models.main

    async def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Генерирует текст на основе произвольного промпта."""
        t0 = time.perf_counter()
        metrics = get_metrics_collector()

        try:
            with traced_operation("llm.generate", {"model": self.model}):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
                result = response.choices[0].message.content or ""

                duration = time.perf_counter() - t0
                tokens_in = len(prompt) // 4
                tokens_out = len(result) // 4
                metrics.record_llm_call("generate", duration, tokens_in, tokens_out, self.model)

                return result
        except Exception as e:
            metrics.record_llm_call(
                "generate", time.perf_counter() - t0, 0, 0, self.model, False, str(e)
            )
            logger.error("Error in LLMClient.generate: %s", e)
            return ""

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> BaseModel:
        """Генерирует структурированный ответ на основе списка сообщений."""
        t0 = time.perf_counter()
        metrics = get_metrics_collector()

        try:
            with traced_operation("llm.generate_structured", {"model": self.model}):
                response = await self.client.chat.completions.parse(
                    model=self.model,
                    messages=messages,
                    response_format=response_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                result = response.choices[0].message.parsed

                if result is None:
                    raise ValueError(f"Failed to parse response into {response_model.__name__}")

                duration = time.perf_counter() - t0
                # Approximate token counting
                tokens_in = sum(len(m["content"]) for m in messages) // 4
                tokens_out = len(str(result)) // 4
                metrics.record_llm_call(
                    "generate_structured", duration, tokens_in, tokens_out, self.model
                )

                return result
        except Exception as e:
            metrics.record_llm_call(
                "generate_structured", time.perf_counter() - t0, 0, 0, self.model, False, str(e)
            )
            logger.error("Error in LLMClient.generate_structured: %s", e)
            raise

    async def check_health(self) -> bool:
        """Проверяет доступность LLM API."""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning("LLM API unavailable: %s", e)
            return False
