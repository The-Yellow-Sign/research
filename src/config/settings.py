"""Конфигурация приложения через Pydantic Settings.

Автоматически загружает переменные окружения из .env файла.
Реализует валидацию типов и fail-fast принцип.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения.

    Автоматически загружает из переменных окружения.
    Приоритет: env vars > .env file > defaults.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @computed_field
    @property
    def project_root(self) -> Path:
        """Корневая директория проекта."""
        return Path(__file__).parent.parent.parent

    @computed_field
    @property
    def source_dir(self) -> Path:
        """Директория с исходными документами."""
        return self.project_root / "devops-playbooks"

    milvus_host: str = Field(default="localhost", description="Хост Milvus")
    milvus_port: str = Field(default="19530", description="Порт Milvus")
    milvus_collection: str = Field(default="devops_docs_v3", description="Название коллекции")
    milvus_batch_size: int = Field(default=128, description="Размер батча для индексации")

    opensearch_host: str = Field(default="localhost", description="Хост OpenSearch")
    opensearch_port: int = Field(default=9200, description="Порт OpenSearch")
    opensearch_index: str = Field(default="devops_codes_v3", description="Индекс children")
    opensearch_parent_index: str = Field(default="devops_parents_v1", description="Индекс parents")

    embedding_model_name: str = Field(
        default="ai-forever/FRIDA",
        description="Модель эмбеддингов (FRIDA — русскоязычная)",
    )
    doc_prefix: str = Field(default="search_document: ", description="Префикс для документов")
    query_prefix: str = Field(default="search_query: ", description="Префикс для запросов")

    reranker_model_name: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Модель реранкера",
    )
    rerank_max_chars: int = Field(default=1500, description="Максимум символов для реранкинга")

    llm_base_url: str = Field(
        default="http://localhost:8000/v1",
        description="URL OpenAI-совместимого API (vLLM)",
    )
    llm_model: str = Field(
        default="cyankiwi/Qwen3-Next-80B-A3B-Instruct-AWQ-4bit",
        description="Название LLM модели",
    )
    llm_api_key: str = Field(
        default="dummy-local-key",
        description="API ключ LLM (для локальных моделей может быть любым)",
    )

    vllm_reranker_url: str = Field(
        default="http://localhost:8001/v1",
        description="URL vLLM сервера для LLM-реранкера (опционально)",
    )

    chunk_size: int = Field(default=600, description="Размер чанка")
    min_chunk_chars: int = Field(default=50, description="Минимум символов в чанке")
    code_block_pattern: str = Field(
        default=r"```[^\n]*\n(.*?)```",
        description="Паттерн для блоков кода",
    )

    @computed_field
    @property
    def chunk_overlap(self) -> int:
        """Перекрытие чанков (25% от размера)."""
        return int(self.chunk_size * 0.25)

    top_k_milvus: int = Field(default=15, description="Top-K для Milvus")
    top_k_opensearch: int = Field(default=15, description="Top-K для OpenSearch")
    final_top_k: int = Field(
        default=10,
        description="Финальный Top-K после BGE реранкинга (LLM отберёт из них топ-5)",
    )
    rrf_k: int = Field(default=60, description="Константа RRF для слияния результатов поиска")

    min_relevance_score: int = Field(default=3, description="Минимальный score LLM-фильтра (0-5)")
    llm_concurrency_limit: int = Field(default=3, description="Лимит параллельных LLM вызовов")

    rag_mode: Literal["basic", "llm_rerank", "full"] = Field(
        default="llm_rerank",
        description=(
            "Режим работы RAG: basic (только BGE), llm_rerank (BGE+LLM), full (BGE+LLM+Summary)"
        ),
    )

    llm_timeout: float = Field(default=60.0, description="Таймаут LLM запросов (секунды)")
    max_context_chars: int = Field(default=16000, description="Макс. длина контекста (символы)")

    circuit_failure_threshold: int = Field(
        default=3,
        description="Количество ошибок для открытия Circuit Breaker",
    )
    circuit_recovery_timeout: int = Field(
        default=30,
        description="Время восстановления Circuit Breaker (секунды)",
    )
    llm_max_retries: int = Field(default=3, description="Максимум повторов LLM запросов")
    db_max_retries: int = Field(default=2, description="Максимум повторов запросов к БД")
    prometheus_enabled: bool = Field(default=True, description="Включить Prometheus метрики")

    metrics_buffer_size: int = Field(default=10000, description="Макс. записей в буфере метрик")

    otlp_endpoint: str | None = Field(
        default=None,
        description="OTLP endpoint для трейсинга (если None — трейсинг отключён)",
    )
    otlp_service_name: str = Field(
        default="rag-service",
        description="Название сервиса для трейсинга",
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Окружение",
    )

    openrouter_api_key: str = Field(
        default="",
        description="API ключ OpenRouter",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL OpenRouter API",
    )
    eval_rag_model: str = Field(
        default="qwen/qwen3-32b",
        description="Модель для генерации ответов в evaluation",
    )
    eval_reranking_model: str = Field(
        default="qwen/qwen3-8b",
        description="Модель для LLM reranking в evaluation",
    )
    eval_judge_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Модель-судья для evaluation",
    )
    ner_fallback_model: str = Field(
        default="qwen/qwen3-4b:free",
        description="Модель для NER fallback через OpenRouter (когда GLiNER не справился)",
    )
    query_expansion_model: str = Field(
        default="qwen/qwen3-8b",
        description="Модель для Query Expansion через OpenRouter",
    )

    ragas_timeout: int = Field(default=600, description="Таймаут RAGAS evaluation (секунды)")
    ragas_max_retries: int = Field(default=15, description="Максимум повторов для RAGAS")
    ragas_max_workers: int = Field(default=2, description="Параллельные workers RAGAS")

    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Разрешённые CORS origins",
    )


settings = Settings()
