"""Port для LLM-клиента.

Определяет абстрактный интерфейс для взаимодействия с языковыми моделями.
Реализации (Adapters) находятся в infrastructure/llm/.
"""

from typing import Protocol

from pydantic import BaseModel


class LLMPort(Protocol):
    """Абстракция для LLM-клиента.

    Определяет контракт для всех LLM-адаптеров (OpenAI, Anthropic, etc.).
    Позволяет подменять реализацию без изменения бизнес-логики.
    """

    async def check_health(self) -> bool:
        """Проверяет доступность LLM API.

        Returns:
            True если API доступно.

        """
        ...

    async def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """Генерирует текст на основе произвольного промпта."""
        ...

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> BaseModel:
        """Генерирует структурированный ответ на основе списка сообщений.

        Args:
            messages: Список сообщений (role/content).
            response_model: Класс Pydantic модели для парсинга.
            max_tokens: Максимальное количество токенов генерации.
            temperature: Температура генерации (0.0 для детерминированности).

        Returns:
            Экземпляр response_model.

        """
        ...
