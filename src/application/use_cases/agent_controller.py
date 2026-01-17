"""AgentController — главный оркестратор ReAct-цикла.

Реализует паттерн ReAct (Reason + Act) для агентного RAG.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

from pydantic import BaseModel

from src.application.prompts.agent_prompts import get_agent_prompts
from src.application.tools import BaseTool
from src.config import LLM_MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)


class AgentEventType(str, Enum):
    """Типы событий для streaming."""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    ERROR = "error"


@dataclass
class AgentEvent:
    """Событие агента для streaming."""

    type: AgentEventType
    content: str = ""
    tool: str | None = None
    params: dict[str, Any] | None = None
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Конвертирует событие в словарь."""
        return {
            "type": self.type.value,
            "content": self.content,
            "tool": self.tool,
            "params": self.params,
            "sources": self.sources,
        }

    def json(self) -> str:
        """Сериализует событие в JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AgentThought(BaseModel):
    """Структура мысли агента."""

    thought: str
    action: str
    params: dict[str, Any] = {}


@dataclass
class AgentResponse:
    """Финальный ответ агента."""

    answer: str
    sources: list[str]
    steps: int
    total_time_sec: float



class AgentController:
    """ReAct Agent для DevOps RAG.

    Координирует цикл think → act → observe → decide.
    """

    MAX_ITERATIONS = 5
    TIMEOUT_SEC = 60.0

    def __init__(
        self,
        tools: list[BaseTool],
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.tools = {t.name: t for t in tools}
        self.api_key = api_key or OPENROUTER_API_KEY
        self.base_url = base_url or OPENROUTER_BASE_URL
        self.model = model or LLM_MODEL

        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def run(self, query: str, history: list[dict[str, str]] | None = None) -> AgentResponse:
        """Выполняет ReAct loop синхронно.

        Args:
            query: Запрос пользователя.
            history: История диалога (опционально).

        Returns:
            AgentResponse с финальным ответом.

        """
        start_time = time.perf_counter()
        observations: list[str] = []
        sources: list[str] = []

        for step in range(self.MAX_ITERATIONS):
            try:
                is_last_step = step == self.MAX_ITERATIONS - 1
                thought = await self._think(
                    query, observations, step=step + 1, force_final=is_last_step
                )
                logger.info("Step %d: action=%s", step + 1, thought.action)

                if thought.action == "final_answer":
                    answer = thought.params.get("answer", "")
                    sources = thought.params.get("sources", [])
                    return AgentResponse(
                        answer=answer,
                        sources=sources,
                        steps=step + 1,
                        total_time_sec=time.perf_counter() - start_time,
                    )

                if thought.action not in self.tools:
                    observations.append(f"Ошибка: инструмент '{thought.action}' не найден")
                    continue

                tool = self.tools[thought.action]
                result = await asyncio.wait_for(
                    tool.execute(**thought.params),
                    timeout=self.TIMEOUT_SEC / self.MAX_ITERATIONS,
                )

                observation = f"[{thought.action}] "
                if result.success:
                    observation += result.data[:2000]
                else:
                    observation += f"Ошибка: {result.error}"

                observations.append(observation)

            except asyncio.TimeoutError:
                observations.append(f"Timeout при выполнении {thought.action}")
            except Exception as e:
                logger.error("Agent step error: %s", e)
                observations.append(f"Ошибка: {e}")

        fallback_msg = (
            "Не удалось найти ответ за отведённое количество шагов. "
            "Попробуйте переформулировать запрос."
        )
        return AgentResponse(
            answer=fallback_msg,
            sources=[],
            steps=self.MAX_ITERATIONS,
            total_time_sec=time.perf_counter() - start_time,
        )

    async def run_stream(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Выполняет ReAct loop с streaming событий.

        Args:
            query: Запрос пользователя.
            history: История диалога.

        Yields:
            AgentEvent с промежуточными результатами.

        """
        observations: list[str] = []
        sources: list[str] = []

        for _step in range(self.MAX_ITERATIONS):
            try:
                thought = await self._think(query, observations, step=_step + 1)

                yield AgentEvent(
                    type=AgentEventType.THINKING,
                    content=thought.thought,
                )

                if thought.action == "final_answer":
                    answer = thought.params.get("answer", "")
                    sources = thought.params.get("sources", [])
                    yield AgentEvent(
                        type=AgentEventType.ANSWER,
                        content=answer,
                        sources=sources,
                    )
                    return

                yield AgentEvent(
                    type=AgentEventType.TOOL_CALL,
                    tool=thought.action,
                    params=thought.params,
                )

                if thought.action not in self.tools:
                    yield AgentEvent(
                        type=AgentEventType.ERROR,
                        content=f"Инструмент '{thought.action}' не найден",
                    )
                    continue

                tool = self.tools[thought.action]
                result = await tool.execute(**thought.params)

                yield AgentEvent(
                    type=AgentEventType.TOOL_RESULT,
                    content=result.data[:1000] if result.success else f"Ошибка: {result.error}",
                )

                observation = f"[{thought.action}] "
                if result.success:
                    observation += result.data[:2000]
                else:
                    observation += f"Ошибка: {result.error}"

                observations.append(observation)

            except Exception as e:
                logger.error("Agent stream error: %s", e)
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    content=str(e),
                )

        yield AgentEvent(
            type=AgentEventType.ANSWER,
            content="Не удалось найти ответ за отведённое количество шагов.",
            sources=[],
        )

    async def _think(
        self,
        query: str,
        observations: list[str],
        step: int = 1,
        force_final: bool = False,
    ) -> AgentThought:
        """Генерирует следующее действие через LLM.

        Args:
            query: Исходный запрос.
            observations: История наблюдений.
            step: Текущий номер шага.
            force_final: Принудительно сгенерировать final_answer.

        Returns:
            AgentThought с action и params.

        """
        if force_final and observations:
            logger.info("Forcing final_answer on last step")
            context = "\n".join(observations[-3:])[:4000]
            return AgentThought(
                thought="Последний шаг, формирую ответ из собранной информации",
                action="final_answer",
                params={
                    "answer": f"На основе найденной информации:\n\n{context}",
                    "sources": [],
                },
            )

        obs_text = "\n".join(observations) if observations else "Пока нет действий."

        prompts = get_agent_prompts()
        urgency_hint = prompts.get_urgency_hint(step, threshold=3)

        prompt = prompts.think_template.format(
            query=query,
            observations=obs_text,
            step=step,
            max_steps=self.MAX_ITERATIONS,
            urgency_hint=urgency_hint,
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        logger.info("Raw LLM response (first 500 chars):\n%s", content[:500])

        return self._parse_llm_response(content, observations, query)

    def _parse_llm_response(
        self,
        content: str,
        observations: list[str],
        query: str,
    ) -> AgentThought:
        """Парсит ответ LLM и возвращает AgentThought.

        Args:
            content: Сырой ответ LLM.
            observations: История наблюдений.
            query: Исходный запрос.

        Returns:
            AgentThought с action и params.

        """
        import re

        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            if "<think>" in content:
                think_match = re.search(r"</think>\s*(.*)", content, re.DOTALL)
                if think_match:
                    content = think_match.group(1).strip()
                    logger.info("After removing <think>: %s", content[:300])

            data = json.loads(content)
            action = data.get("action")
            params = data.get("params", {})
            logger.info("Parsed action=%s, params=%s", action, str(params)[:200])

            if not action and observations:
                return self._build_fallback_thought(observations)

            return AgentThought(
                thought=data.get("thought", ""),
                action=action or "final_answer",
                params=params,
            )
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse: %s\nContent: %s", e, content[:500])
            return self._handle_parse_error(content, observations, query)

    def _build_fallback_thought(self, observations: list[str]) -> AgentThought:
        """Создаёт fallback ответ из наблюдений."""
        context = "\n".join(observations[-3:])[:4000]
        return AgentThought(
            thought="Генерирую ответ из собранных данных",
            action="final_answer",
            params={"answer": f"На основе информации:\n\n{context}", "sources": []},
        )

    def _handle_parse_error(
        self,
        content: str,
        observations: list[str],
        query: str,
    ) -> AgentThought:
        """Обрабатывает ошибку парсинга JSON."""
        import re

        if '"answer":' in content:
            match = re.search(r'"answer":\s*"([^"]*)', content)
            if match:
                return AgentThought(
                    thought="Извлечён частичный ответ",
                    action="final_answer",
                    params={"answer": match.group(1), "sources": []},
                )

        if observations:
            return self._build_fallback_thought(observations)

        return AgentThought(
            thought="Не удалось распарсить, пробую поиск",
            action="rag_search",
            params={"query": query},
        )
