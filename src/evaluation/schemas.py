"""Pydantic-схемы для системы оценки RAG."""

from pydantic import BaseModel, Field


class RetrievedContext(BaseModel):
    """Один retrieved документ."""

    source: str = Field(..., description="Имя файла источника")
    content: str = Field(..., description="Содержимое документа")
    score: float = Field(..., description="Скор релевантности")


class RAGOutput(BaseModel):
    """Выход RAG-системы для одного вопроса."""

    generated_answer: str = Field(..., description="Сгенерированный ответ")
    rewritten_query: str = Field(default="", description="Переписанный запрос")
    retrieved_contexts: list[RetrievedContext] = Field(
        default_factory=list, description="Найденные документы"
    )
    latency_sec: float = Field(default=0.0, description="Общее время pipeline")
    answer_type: str = Field(default="final_answer", description="Тип ответа")
    timings: dict[str, float] | None = Field(
        default=None, description="Детальные таймеры по этапам pipeline"
    )


class EvaluationResult(BaseModel):
    """Полный результат оценки одного вопроса."""

    id: str = Field(..., description="ID вопроса")
    question: str = Field(..., description="Вопрос")
    expected_answer: str = Field(..., description="Эталонный ответ")
    source_file: str = Field(default="", description="Исходный файл")
    difficulty: str = Field(default="", description="Сложность")
    category: str = Field(default="", description="Категория")

    rag_output: RAGOutput | None = Field(default=None, description="Результат RAG")

    ragas_scores: dict[str, float] | None = Field(default=None, description="Оценки RAGAS")

    error: str | None = Field(default=None, description="Ошибка, если была")


class EvaluationSummary(BaseModel):
    """Сводка по всей оценке."""

    total_questions: int = Field(default=0)
    successful: int = Field(default=0)
    failed: int = Field(default=0)

    avg_context_recall: float = Field(default=0.0)
    avg_context_precision: float = Field(default=0.0)
    avg_faithfulness: float = Field(default=0.0)
    avg_answer_relevancy: float = Field(default=0.0)

    avg_rag_latency_sec: float = Field(default=0.0)

    avg_query_expansion_sec: float = Field(default=0.0)
    avg_retrieve_sec: float = Field(default=0.0)
    avg_rerank_sec: float = Field(default=0.0)
    avg_llm_analysis_sec: float = Field(default=0.0)
    avg_llm_generation_sec: float = Field(default=0.0)


class EvaluationReport(BaseModel):
    """Полный отчёт об оценке."""

    metadata: dict = Field(default_factory=dict)
    summary: EvaluationSummary = Field(default_factory=EvaluationSummary)
    by_category: dict[str, EvaluationSummary] = Field(default_factory=dict)
    by_difficulty: dict[str, EvaluationSummary] = Field(default_factory=dict)
    results: list[EvaluationResult] = Field(default_factory=list)
