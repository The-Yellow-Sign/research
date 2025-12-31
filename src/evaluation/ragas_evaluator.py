"""RAGAS-оценка системы RAG.

Использует библиотеку RAGAS для стандартизированных метрик RAG:
- context_recall: Покрытие эталонного ответа
- context_precision: Релевантность извлеченного контекста
- faithfulness: Фактическая согласованность с контекстом
- answer_relevancy: Релевантность ответа запросу
"""

import logging
from typing import Any

from datasets import Dataset
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
)
from sentence_transformers import SentenceTransformer

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddings(BaseRagasEmbeddings):
    """RAGAS-совместимая обертка для SentenceTransformer."""

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed_query(self, text: str) -> list[float]:
        """Встраивание (embedding) одного запроса."""
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Встраивание (embedding) нескольких документов."""
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    async def aembed_query(self, text: str) -> list[float]:
        """Асинхронная версия embed_query."""
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Асинхронная версия embed_documents."""
        return self.embed_documents(texts)


class RagasEvaluator:
    """Оценщик систем RAG на основе RAGAS."""

    def __init__(self, model: str | None = None) -> None:
        """Инициализация оценщика с LLM OpenRouter."""
        self.model = model or settings.eval_judge_model

        self.llm = ChatOpenAI(
            model=self.model,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=settings.openrouter_base_url,
            temperature=0.1,
            timeout=300,
            max_retries=3,
            max_tokens=16000,
        )
        self.ragas_llm = LangchainLLMWrapper(self.llm)

        self.ragas_embeddings = SentenceTransformerEmbeddings(settings.embedding_model_name)

        logger.info("RagasEvaluator initialized: model=%s", self.model)

    def prepare_dataset(self, items: list[dict[str, Any]]) -> Dataset:
        """Преобразование элементов золотого датасета в формат RAGAS."""
        data = {
            "user_input": [],
            "response": [],
            "reference": [],
            "retrieved_contexts": [],
        }

        for item in items:
            data["user_input"].append(item.get("question", ""))
            data["response"].append(item.get("generated_answer", ""))
            data["reference"].append(item.get("expected_answer", ""))

            contexts = item.get("retrieved_contexts", [])
            if isinstance(contexts, list):
                context_texts = [
                    c.get("content", str(c)) if isinstance(c, dict) else str(c)
                    for c in contexts
                ]
            else:
                context_texts = [str(contexts)] if contexts else []

            data["retrieved_contexts"].append(context_texts)

        return Dataset.from_dict(data)

    async def evaluate_batch(
        self,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Оценка партии элементов с использованием RAGAS."""
        if not items:
            return {"scores": [], "summary": {}}

        dataset = self.prepare_dataset(items)

        logger.info("Running RAGAS evaluation on %d items...", len(items))


        metrics = [
            context_recall,
            context_precision,
            faithfulness,
        ]


        from ragas.run_config import RunConfig

        run_config = RunConfig(
            timeout=600,
            max_retries=5,
            max_wait=120,
            max_workers=4,
        )

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=self.ragas_llm,
            embeddings=self.ragas_embeddings,
            run_config=run_config,
        )


        df = result.to_pandas()
        scores = df.to_dict(orient="records")


        summary = {
            "context_recall": float(df["context_recall"].mean()) if "context_recall" in df else 0.0,
            "context_precision": (
                float(df["context_precision"].mean()) if "context_precision" in df else 0.0
            ),
            "faithfulness": float(df["faithfulness"].mean()) if "faithfulness" in df else 0.0,
            "answer_relevancy": 0.0,
        }

        logger.info(
            "RAGAS complete: recall=%.2f, precision=%.2f, faith=%.2f",
            summary["context_recall"],
            summary["context_precision"],
            summary["faithfulness"],
        )

        return {"scores": scores, "summary": summary}
