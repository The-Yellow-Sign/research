"""LLM-клиент для evaluation через OpenRouter.

Совместим с интерфейсом LLMClient — можно передать в RAGService.
"""

import logging
import time

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel

from src.application.prompts import (
    BATCH_SUMMARY_PROMPT,
    RERANKER_PROMPT_BATCH,
    RERANKER_PROMPT_SINGLE,
    SUMMARY_PROMPT,
    SYSTEM_ANALYZER,
    SYSTEM_CLARIFY,
    SYSTEM_MAIN,
    SYSTEM_QUERY_EXPANSION,
    format_analysis_prompt,
    format_query_rewrite_prompt,
)
from src.config.settings import settings
from src.config.telemetry import traced_operation
from src.domain.models import (
    DocAnalysis,
    QueryExpansion,
    RerankerBatchResult,
    RerankerResult,
)

logger = logging.getLogger(__name__)


class EvalLLMClient:
    """LLM-клиент для evaluation через OpenRouter API.

    Совместим с LLMClient по интерфейсу для использования в RAGService.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """Инициализирует клиент.

        Args:
            api_key: OpenRouter API ключ.
            base_url: OpenRouter base URL.
            model: Модель для RAG (eval_rag_model).

        """
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self.model = model or settings.eval_rag_model

        if not self.api_key:
            raise ValueError("OpenRouter API ключ не задан (OPENROUTER_API_KEY)")

        self._http_client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=200,
                max_keepalive_connections=50,
            ),
            timeout=httpx.Timeout(timeout=120.0),
        )
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=self._http_client,
        )

        logger.info("EvalLLMClient инициализирован: model=%s (pool=200)", self.model)

    def _get_routing_config(self) -> dict:
        """Возвращает настройки маршрутизации для OpenRouter."""
        return {"provider": {"sort": "throughput", "allow_fallbacks": True}}

    async def expand_query(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> QueryExpansion:
        """Расширяет запрос.

        Args:
            query: Запрос пользователя.
            history: История диалога.

        Returns:
            QueryExpansion с основным запросом и вариациями.

        """
        recent = history[-4:] if history else []
        history_text = (
            "\n".join(
                [
                    f"{'User' if msg['role'] == 'user' else 'Bot'}: {msg['content'][:200]}..."
                    for msg in recent
                ]
            )
            if recent
            else "Нет истории."
        )

        t0 = time.perf_counter()
        try:
            with traced_operation("eval_llm.expand_query", {"model": self.model}):
                response = await self.client.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_QUERY_EXPANSION},
                        {
                            "role": "user",
                            "content": format_query_rewrite_prompt(history_text, query),
                        },
                    ],
                    response_format=QueryExpansion,
                    temperature=0.0,
                    max_tokens=500,
                    extra_body=self._get_routing_config(),
                )
                result = response.choices[0].message.parsed
                duration = time.perf_counter() - t0
                logger.debug("Query expansion (%.2fs): %s", duration, result.rewritten_query[:50])
                return result
        except Exception as e:
            logger.warning("Ошибка расширения запроса: %s", e)

            return QueryExpansion(rewritten_query=query, variations=[query, query])

    async def analyze_document(
        self,
        content: str,
        query: str,
    ) -> DocAnalysis | None:
        """Анализирует документ на релевантность через LLM.

        Args:
            content: Текст документа.
            query: Запрос пользователя для оценки релевантности.

        Returns:
            DocAnalysis с оценкой релевантности или None при ошибке.

        """
        t0 = time.perf_counter()
        try:
            with traced_operation("eval_llm.analyze_doc", {"model": self.model}):
                response = await self.client.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_ANALYZER},
                        {"role": "user", "content": format_analysis_prompt(query, content)},
                    ],
                    response_format=DocAnalysis,
                    temperature=0.0,
                    max_tokens=2000,
                    extra_body=self._get_routing_config(),
                )
                result = response.choices[0].message.parsed
                duration = time.perf_counter() - t0
                logger.debug("Doc analysis (%.2fs): score=%d", duration, result.relevance_score)
                return result
        except Exception as e:
            logger.warning("Ошибка анализа документа: %s", e)
            return None

    async def generate_clarifying_question(self, original_query: str) -> str:
        """Генерирует уточняющий вопрос.

        Args:
            original_query: Исходный запрос.

        Returns:
            Уточняющий вопрос.

        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_CLARIFY},
                    {"role": "user", "content": original_query},
                ],
                temperature=0.0,
                max_tokens=500,
                extra_body=self._get_routing_config(),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning("Ошибка генерации уточняющего вопроса: %s", e)
            return "Не могли бы вы уточнить ваш запрос?"

    async def generate_answer(
        self,
        context_xml: str,
        query: str,
    ) -> str:
        """Генерирует финальный ответ на основе контекста.

        Args:
            context_xml: XML-контекст с документами.
            query: Запрос пользователя.

        Returns:
            Сгенерированный ответ.

        Raises:
            RuntimeError: При ошибке генерации.

        """
        t0 = time.perf_counter()
        try:
            with traced_operation("eval_llm.generate", {"model": self.model}):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_MAIN},
                        {
                            "role": "user",
                            "content": f"CONTEXT:\n{context_xml}\n\nQUESTION: {query}",
                        },
                    ],
                    stream=False,
                    temperature=0.0,
                    extra_body=self._get_routing_config(),
                )
                answer = response.choices[0].message.content or ""
                duration = time.perf_counter() - t0
                logger.debug("Answer generation (%.2fs): %d chars", duration, len(answer))
                return answer
        except Exception as e:
            logger.error("Ошибка генерации LLM: %s", e)
            raise RuntimeError(f"Ошибка генерации ответа: {e}") from e

    async def rerank_batch(
        self,
        query: str,
        documents: list[dict],
        batch_size: int = 5,
    ) -> list[float]:
        """Реранкинг документов через LLM.

        Args:
            query: Запрос пользователя.
            documents: Список документов с 'raw_content'.
            batch_size: Размер батча.

        Returns:
            Список оценок релевантности [0.0-1.0].

        """
        scores = []

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            if len(batch) == 1:
                content = batch[0].get("raw_content", "")[:3000]
                prompt = (
                    f"{RERANKER_PROMPT_SINGLE}\n\nQuery: {query}\n\nDocument:\n---\n{content}\n---"
                )

                try:
                    response = await self.client.chat.completions.parse(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format=RerankerResult,
                        temperature=0.0,
                        max_tokens=3000,
                        extra_body=self._get_routing_config(),
                    )
                    result = response.choices[0].message.parsed
                    scores.append(result.relevance_score if result else 0.5)
                except Exception as e:
                    logger.warning("Rerank single error: %s", e)
                    scores.append(0.5)
            else:
                blocks_text = ""
                for idx, doc in enumerate(batch, 1):
                    content = doc.get("raw_content", "")[:2000]
                    blocks_text += f"\n[Block {idx}]:\n{content}\n"

                prompt = f"{RERANKER_PROMPT_BATCH}\n\nQuery: {query}\n{blocks_text}"

                try:
                    response = await self.client.chat.completions.parse(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format=RerankerBatchResult,
                        temperature=0.0,
                        max_tokens=500,
                        extra_body=self._get_routing_config(),
                    )
                    result = response.choices[0].message.parsed
                    if result and result.block_rankings:
                        for ranking in result.block_rankings[: len(batch)]:
                            scores.append(ranking.relevance_score)
                        while len(scores) < i + len(batch):
                            scores.append(0.5)
                    else:
                        scores.extend([0.5] * len(batch))
                except Exception as e:
                    logger.warning("Rerank batch error: %s", e)
                    scores.extend([0.5] * len(batch))

        return scores

    async def summarize_document(
        self,
        content: str,
    ) -> str:
        """Сжимает документ.

        Реализация для тестов - используем основного клиента или возвращаем оригинал.
        """
        if not content:
            return ""

        try:
            prompt = f"{SUMMARY_PROMPT}\n\nТекст:\n---\n{content}\n---\nСжатый текст:"

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

            summary = response.choices[0].message.content
            return summary.strip() if summary else content

        except Exception:
            return content

    async def summarize_batch(
        self,
        contents: list[str],
    ) -> list[str]:
        """Batch summarization — сжимает несколько документов за один LLM вызов.

        Args:
            contents: Список текстов документов.

        Returns:
            Список сжатых текстов в том же порядке.

        """
        if not contents:
            return []

        class BatchSummaryResponse(BaseModel):
            summaries: list[str]

        MAX_CHARS_PER_DOC = 2000
        docs_xml = "\n".join(
            [
                f"<doc id='{i}'>{content[:MAX_CHARS_PER_DOC]}</doc>"
                for i, content in enumerate(contents, 1)
            ]
        )

        try:
            response = await self.client.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": BATCH_SUMMARY_PROMPT},
                    {"role": "user", "content": docs_xml},
                ],
                response_format=BatchSummaryResponse,
                temperature=0.3,
                max_tokens=2500,
            )

            result = response.choices[0].message.parsed
            if result and result.summaries:
                if len(result.summaries) == len(contents):
                    logger.info(
                        "Batch summarization: %d документов сжато за 1 вызов",
                        len(contents),
                    )
                    return result.summaries
                else:
                    summaries = list(result.summaries)
                    for i in range(len(summaries), len(contents)):
                        summaries.append(contents[i][:MAX_CHARS_PER_DOC])
                    return summaries

            return contents

        except Exception as e:
            logger.warning("Batch summarization failed: %s", e)
            return contents
