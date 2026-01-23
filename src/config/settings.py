"""Конфигурация приложения через Pydantic Settings.

Автоматически загружает переменные окружения из .env файла.
Реализует валидацию типов и fail-fast принцип.
"""

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGMode(str, Enum):
    """Режимы работы RAG-пайплайна."""

    BASIC = "basic"
    LLM_RERANK = "llm_rerank"
    FULL = "full"


class ModelSettings(BaseModel):
    """Настройки используемых LLM и эмбеддинг-моделей."""

    embedding: str = Field(
        default="ai-forever/FRIDA",
        description="Модель эмбеддингов (FRIDA — русскоязычная)",
    )
    reranker: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Модель реранкера",
    )
    main: str = Field(
        default="qwen/qwen3-next-80b-a3b-instruct",
        description="Основная LLM модель (генерация, рассуждения агента)",
    )
    eval_judge: str = Field(
        default="openai/gpt-4o-mini",
        description="Модель-судья для evaluation (RAGAS)",
    )
    ner_fallback: str = Field(
        default="qwen/qwen3-8b",
        description="Модель для NER fallback через OpenRouter",
    )
    query_expansion: str = Field(
        default="qwen/qwen3-8b",
        description="Модель для Query Expansion через OpenRouter",
    )


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
    milvus_port: int = Field(default=19530, description="Порт Milvus")
    milvus_collection: str = Field(default="devops_docs_v3", description="Название коллекции")
    milvus_batch_size: int = Field(default=128, description="Размер батча для индексации")

    opensearch_host: str = Field(default="localhost", description="Хост OpenSearch")
    opensearch_port: int = Field(default=9200, description="Порт OpenSearch")
    opensearch_index: str = Field(default="devops_codes_v3", description="Индекс children")
    opensearch_parent_index: str = Field(default="devops_parents_v1", description="Индекс parents")
    opensearch_files_index: str = Field(default="files_v1", description="Индекс реестра файлов")

    models: ModelSettings = Field(default_factory=ModelSettings)

    doc_prefix: str = Field(default="search_document: ", description="Префикс для документов")
    query_prefix: str = Field(default="search_query: ", description="Префикс для запросов")
    embedding_model_max_tokens: int = Field(
        default=512,
        description="Максимальное количество токенов для эмбеддинг-модели",
    )

    rerank_max_chars: int = Field(default=1500, description="Максимум символов для реранкинга")

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

    rag_mode: RAGMode = Field(
        default=RAGMode.BASIC,
        description=(
            "Режим работы RAG: basic (только BGE), llm_rerank (BGE+LLM), full (BGE+LLM+Summary)"
        ),
    )

    @computed_field
    @property
    def use_llm_reranking(self) -> bool:
        """Использовать LLM для реранкинга документов."""
        return self.rag_mode in (RAGMode.LLM_RERANK, RAGMode.FULL)

    @computed_field
    @property
    def use_summarization(self) -> bool:
        """Сжимать документы перед генерацией ответа."""
        return self.rag_mode == RAGMode.FULL

    vector_weight: float = Field(default=0.3, description="Вес vector score при LLM реранкинге")
    llm_rerank_weight: float = Field(default=0.7, description="Вес LLM score при реранкинге")
    llm_final_top_k: int = Field(default=5, description="Финальный top-K после LLM реранкинга")
    min_relevance_threshold: float = Field(default=0.3, description="Минимальный порог LLM score")

    llm_timeout: float = Field(default=60.0, description="Таймаут LLM запросов (секунды)")
    max_context_chars: int = Field(default=16000, description="Макс. длина контекста (символы)")

    metrics_buffer_size: int = Field(default=10000, description="Макс. записей в буфере метрик")

    agent_max_iterations: int = Field(
        default=5, description="Максимальное количество итераций агента"
    )
    agent_timeout: float = Field(default=60.0, description="Таймаут агента (секунды)")
    agent_reflection_enabled: bool = Field(
        default=True, description="Включить саморефлексию агента"
    )
    agent_reflection_min_sources: int = Field(
        default=3, description="Минимум источников для включения рефлексии"
    )
    agent_reflection_min_steps: int = Field(
        default=2, description="Минимум шагов для включения рефлексии"
    )
    agent_max_system_errors: int = Field(
        default=3, description="Максимальное количество системных ошибок (TOKEN_LIMIT и т.д.)"
    )
    llm_retry_attempts: int = Field(default=3, description="Количество повторных попыток LLM")
    llm_retry_base_delay: float = Field(default=1.0, description="Базовая задержка retry (секунды)")
    llm_retry_max_delay: float = Field(
        default=10.0, description="Максимальная задержка retry (секунды)"
    )

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

    openrouter_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="API ключ OpenRouter",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL OpenRouter API",
    )

    tavily_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="API ключ Tavily",
    )

    @model_validator(mode="after")
    def validate_api_keys(self) -> "Settings":
        """Проверяет наличие API ключей в режиме production."""
        if self.environment == "production":
            if not self.openrouter_api_key.get_secret_value():
                raise ValueError("OPENROUTER_API_KEY must be set in production environment")
        return self

    ragas_timeout: int = Field(default=600, description="Таймаут RAGAS evaluation (секунды)")
    ragas_max_retries: int = Field(default=15, description="Максимум повторов для RAGAS")
    ragas_max_workers: int = Field(default=2, description="Параллельные workers RAGAS")

    summary_max_chars_per_doc: int = Field(
        default=2000, description="Макс. символов на документ для суммаризации"
    )
    rag_search_content_limit: int = Field(
        default=1500, description="Лимит контента в результатах RAG-поиска"
    )
    ner_text_limit: int = Field(default=2000, description="Лимит текста для NER-экстракции")

    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Разрешённые CORS origins",
    )

    agent_observation_max_chars: int = Field(
        default=1500, description="Лимит символов для одного наблюдения в ReAct цикле"
    )
    agent_result_max_chars: int = Field(
        default=2000, description="Лимит символов для общего результата выполнения шага"
    )
    agent_context_max_chars: int = Field(
        default=5000, description="Максимальная длина контекста для инструментов проверки"
    )
    agent_observation_max_tokens: int = Field(
        default=8000, description="Максимальное количество токенов для наблюдений агента"
    )
    agent_max_tokens: int = Field(
        default=10000, description="Максимальное количество токенов для генерации агента"
    )
    session_max_context_chars: int = Field(
        default=1000, description="Лимит символов для суммаризации контекста сессии"
    )
    session_ttl_sec: int = Field(default=3600, description="Время жизни сессии в секундах")
    code_exec_max_output: int = Field(
        default=2000, description="Максимальный вывод выполнения кода"
    )
    tool_cache_ttl: int = Field(default=300, description="TTL кэша инструментов (секунды)")


settings = Settings()
