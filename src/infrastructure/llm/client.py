"""Клиент для взаимодействия с LLM.

Инкапсулирует все операции с языковой моделью:
- Расширение запросов (Query Expansion)
- Анализ релевантности документов
- Генерация уточняющих вопросов
- Генерация финальных ответов
"""

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

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
from src.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT,
    MAX_CONTEXT_CHARS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    QUERY_EXPANSION_MODEL,
)
from src.config.metrics import get_metrics_collector
from src.config.telemetry import traced_operation
from src.domain.models import DocAnalysis, QueryExpansion, RerankerBatchResult, RerankerResult

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент для работы с LLM через OpenAI-совместимый API.

    Предоставляет высокоуровневые методы для RAG-операций.
    Использует Structured Output для надёжного парсинга ответов.
    """

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        """Инициализирует LLM-клиент.

        Args:
            client: Опциональный AsyncOpenAI клиент. Если None, создаётся автоматически.

        """
        if client is not None:
            self.client = client
            self._http_client = None
            logger.info("Используется переданный LLM-клиент")
        else:
            self._http_client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=200,
                    max_keepalive_connections=50,
                ),
                timeout=httpx.Timeout(timeout=LLM_TIMEOUT),
            )
            self.client = AsyncOpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                http_client=self._http_client,
            )
            logger.info("Создан LLM-клиент (timeout=%.0fs, pool=200)", LLM_TIMEOUT)

        self._expand_cache: OrderedDict[str, QueryExpansion] = OrderedDict()
        self._cache_max_size = 100

        self._openrouter_client: AsyncOpenAI | None = None
        if OPENROUTER_API_KEY:
            self._openrouter_client = AsyncOpenAI(
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
            )
            logger.info("OpenRouter client initialized for Query Expansion")

    async def expand_query(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> QueryExpansion:
        """Расширяет запрос с учётом истории диалога.

        Генерирует основной переписанный запрос и 2-3 альтернативных
        формулировки для повышения полноты поиска (Recall).

        Args:
            query: Текущий запрос пользователя.
            history: История диалога (список сообщений).

        Returns:
            QueryExpansion с основным запросом и вариациями.

        """
        cache_key = hashlib.sha256(f"{query}:{len(history)}".encode()).hexdigest()[:16]
        if cache_key in self._expand_cache:
            logger.debug("Query Expansion cache hit: %s", query[:50])
            self._expand_cache.move_to_end(cache_key)
            return self._expand_cache[cache_key]

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
        metrics = get_metrics_collector()

        use_openrouter = self._openrouter_client is not None
        client = self._openrouter_client if use_openrouter else self.client
        model = QUERY_EXPANSION_MODEL if use_openrouter else LLM_MODEL

        try:
            with traced_operation("llm.expand_query", {"model": model}):
                response = await client.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_QUERY_EXPANSION},
                        {
                            "role": "user",
                            "content": format_query_rewrite_prompt(history_text, query),
                        },
                    ],
                    response_format=QueryExpansion,
                    temperature=0.0,
                    max_tokens=300,
                )
                result = response.choices[0].message.parsed

                if result and result.variations:
                    result.variations = [v[:100] for v in result.variations]

                duration = time.perf_counter() - t0
                tokens_in = len(query) // 4 + 200
                tokens_out = len(str(result)) // 4
                metrics.record_llm_call("expand_query", duration, tokens_in, tokens_out, LLM_MODEL)

                self._expand_cache[cache_key] = result
                if len(self._expand_cache) > self._cache_max_size:
                    self._expand_cache.popitem(last=False)

                return result
        except Exception as e:
            metrics.record_llm_call(
                "expand_query", time.perf_counter() - t0, 0, 0, LLM_MODEL, False, str(e)
            )
            logger.warning("Ошибка расширения запроса: %s", e)

            return QueryExpansion(
                rewritten_query=query,
                variations=[query, f"{query} ошибка причина диагностика"],
            )

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
        metrics = get_metrics_collector()
        try:
            response = await self.client.chat.completions.parse(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_ANALYZER},
                    {"role": "user", "content": format_analysis_prompt(query, content)},
                ],
                response_format=DocAnalysis,
                temperature=0.0,
                max_tokens=2000,
            )
            result = response.choices[0].message.parsed
            duration = time.perf_counter() - t0
            tokens_in = len(content) // 4 + len(query) // 4 + 100
            tokens_out = len(str(result)) // 4 if result else 0
            metrics.record_llm_call("analyze_document", duration, tokens_in, tokens_out, LLM_MODEL)
            return result
        except Exception as e:
            metrics.record_llm_call(
                "analyze_document", time.perf_counter() - t0, 0, 0, LLM_MODEL, False, str(e)
            )
            logger.warning("Ошибка анализа документа: %s", e)
            return None

    async def rerank_batch(
        self,
        query: str,
        documents: list[dict],
        batch_size: int = 5,
    ) -> list[float]:
        """Реранкинг документов через LLM (по образцу RAG-Challenge-2).

        Оценивает документы батчами для эффективности.
        Возвращает список оценок 0.0-1.0 для каждого документа.

        Args:
            query: Запрос пользователя.
            documents: Список документов с 'raw_content'.
            batch_size: Размер батча (по умолчанию 3).

        Returns:
            Список оценок релевантности [0.0-1.0].

        """
        scores = []
        batches = [documents[i : i + batch_size] for i in range(0, len(documents), batch_size)]

        tasks = [self._process_batch_rerank(query, batch) for batch in batches]
        results = await asyncio.gather(*tasks)

        for batch_res in results:
            scores.extend(batch_res)

        return scores

    async def _process_batch_rerank(self, query: str, batch_docs: list[dict]) -> list[float]:
        """Обрабатывает один батч документов для реранкинга."""
        batch_scores = []
        if len(batch_docs) == 1:
            content = batch_docs[0].get("raw_content", "")[:3000]
            prompt = f"{RERANKER_PROMPT_SINGLE}\n\nQuery: {query}\n\nDocument:\n---\n{content}\n---"

            try:
                response = await self.client.chat.completions.parse(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format=RerankerResult,
                    temperature=0.0,
                    max_tokens=300,
                )
                result = response.choices[0].message.parsed
                batch_scores.append(result.relevance_score if result else 0.5)
            except Exception as e:
                logger.warning("Rerank single error: %s", e)
                batch_scores.append(0.5)
        else:
            blocks_text = ""
            for idx, doc in enumerate(batch_docs, 1):
                content = doc.get("raw_content", "")[:2000]
                blocks_text += f"\n[Block {idx}]:\n{content}\n"

            prompt = f"{RERANKER_PROMPT_BATCH}\n\nQuery: {query}\n{blocks_text}"

            try:
                response = await self.client.chat.completions.parse(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format=RerankerBatchResult,
                    temperature=0.0,
                    max_tokens=500,
                )
                result = response.choices[0].message.parsed
                if result and result.block_rankings:
                    for ranking in result.block_rankings[: len(batch_docs)]:
                        batch_scores.append(ranking.relevance_score)
                    while len(batch_scores) < len(batch_docs):
                        batch_scores.append(0.5)
                else:
                    batch_scores.extend([0.5] * len(batch_docs))
            except Exception as e:
                logger.warning("Rerank batch error: %s", e)
                batch_scores.extend([0.5] * len(batch_docs))

        return batch_scores

    async def summarize_document(
        self,
        content: str,
    ) -> str:
        """Сжимает текст документа, сохраняя ключевую информацию.

        Использует LLM для генерации саммари (сжатого содержания).
        Если процессинг не удался, возвращает исходный текст.

        Args:
            content: Исходный текст документа.

        Returns:
            Сжатый текст или оригинал в случае ошибки.

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

        except Exception as e:
            logger.warning("Ошибка суммаризации (возвращаем оригинал): %s", e)
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
                    logger.warning(
                        "Batch summarization: получено %d сжатий вместо %d",
                        len(result.summaries),
                        len(contents),
                    )
                    summaries = list(result.summaries)
                    for i in range(len(summaries), len(contents)):
                        summaries.append(contents[i][:MAX_CHARS_PER_DOC])
                    return summaries

            return contents

        except Exception as e:
            logger.warning("Batch summarization failed, returning originals: %s", e)
            return contents

    async def generate_clarifying_question(self, original_query: str) -> str:
        """Генерирует уточняющий вопрос, когда поиск не дал релевантных результатов.

        Args:
            original_query: Исходный запрос пользователя.

        Returns:
            Уточняющий вопрос для пользователя.

        """
        t0 = time.perf_counter()
        metrics = get_metrics_collector()
        try:
            response = await self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_CLARIFY},
                    {"role": "user", "content": original_query},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            result = response.choices[0].message.content
            duration = time.perf_counter() - t0
            metrics.record_llm_call(
                "clarifying_question",
                duration,
                len(original_query) // 4 + 50,
                len(result) // 4 if result else 0,
                LLM_MODEL,
            )
            return result
        except Exception as e:
            metrics.record_llm_call(
                "clarifying_question", time.perf_counter() - t0, 0, 0, LLM_MODEL, False, str(e)
            )
            logger.warning("Ошибка генерации уточняющего вопроса: %s", e)
            return (
                "Не могли бы вы уточнить ваш запрос? "
                "Какую именно технологию или сервис вы имеете в виду?"
            )

    async def generate_answer(
        self,
        context_xml: str,
        query: str,
    ) -> str:
        """Генерирует финальный ответ на основе контекста.

        Использует retry с exponential backoff для transient errors.
        Проверяет и обрезает слишком длинный контекст.

        Args:
            context_xml: XML-контекст с документами.
            query: Запрос пользователя.

        Returns:
            Сгенерированный ответ.

        Raises:
            RuntimeError: При ошибке генерации.

        """
        if len(context_xml) > MAX_CONTEXT_CHARS:
            logger.warning("Context truncated: %d -> %d chars", len(context_xml), MAX_CONTEXT_CHARS)
            context_xml = context_xml[:MAX_CONTEXT_CHARS] + "\n</documents>"

        t0 = time.perf_counter()
        metrics = get_metrics_collector()

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((TimeoutError, ConnectionError)),
            reraise=True,
        )
        async def _call_with_retry():
            return await self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_MAIN},
                    {
                        "role": "user",
                        "content": f"CONTEXT:\n{context_xml}\n\nQUESTION: {query}",
                    },
                ],
                stream=False,
                temperature=0.0,
            )

        try:
            response = await _call_with_retry()
            result = response.choices[0].message.content
            duration = time.perf_counter() - t0
            tokens_in = len(context_xml) // 4 + len(query) // 4 + 200
            tokens_out = len(result) // 4 if result else 0
            metrics.record_llm_call("generate_answer", duration, tokens_in, tokens_out, LLM_MODEL)
            return result
        except Exception as e:
            metrics.record_llm_call(
                "generate_answer", time.perf_counter() - t0, 0, 0, LLM_MODEL, False, str(e)
            )
            logger.error("Ошибка генерации LLM: %s", e)
            raise RuntimeError(f"Ошибка генерации ответа: {e}") from e

    async def check_health(self) -> bool:
        """Проверяет доступность LLM API.

        Returns:
            True если API доступно, False в противном случае.

        """
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning("LLM API недоступен: %s", e)
            return False

    async def generate_answer_stream(
        self,
        context_xml: str,
        query: str,
    ) -> AsyncIterator[str]:
        """Генерирует финальный ответ в режиме streaming.

        Записывает метрики после завершения streaming.
        Проверяет длину контекста.

        Args:
            context_xml: XML-контекст с документами.
            query: Запрос пользователя.

        Yields:
            Токены ответа по мере генерации.

        """
        if len(context_xml) > MAX_CONTEXT_CHARS:
            logger.warning(
                "Context truncated (stream): %d -> %d chars", len(context_xml), MAX_CONTEXT_CHARS
            )
            context_xml = context_xml[:MAX_CONTEXT_CHARS] + "\n</documents>"

        t0 = time.perf_counter()
        metrics = get_metrics_collector()
        total_chars = 0

        try:
            response = await self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_MAIN},
                    {
                        "role": "user",
                        "content": f"CONTEXT:\n{context_xml}\n\nQUESTION: {query}",
                    },
                ],
                stream=True,
                temperature=0.0,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_chars += len(content)
                    yield content

            duration = time.perf_counter() - t0
            tokens_in = len(context_xml) // 4 + len(query) // 4 + 200
            tokens_out = total_chars // 4
            metrics.record_llm_call(
                "generate_answer_stream", duration, tokens_in, tokens_out, LLM_MODEL
            )
        except Exception as e:
            metrics.record_llm_call(
                "generate_answer_stream", time.perf_counter() - t0, 0, 0, LLM_MODEL, False, str(e)
            )
            logger.error("Ошибка streaming генерации: %s", e)
            yield f"[Ошибка генерации: {e}]"
