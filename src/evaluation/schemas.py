"""Pydantic-схемы для системы оценки RAG."""

from pydantic import BaseModel, Field


class RetrievedContext(BaseModel):
    """Один retrieved документ."""

    source: str = Field(..., description="Имя файла источника")
    content: str = Field(..., description="Содержимое документа")
    score: float = Field(..., description="Скор релевантности")


class Footnote(BaseModel):
    """Сноска на источник."""

    doc_id: int
    service: str
    title: str
    source_file: str
    quote: str
    source_type: str = "doc"
    header_path: str | None = None
    url: str | None = None

    @property
    def id(self) -> int:
        """Alias для doc_id для обратной совместимости с UI."""
        return self.doc_id


class TraceStep(BaseModel):
    """Шаг трассировки агента."""

    step: int
    thought: str
    action: str
    params: dict = Field(default_factory=dict)
    observation: str | None = None


class RAGOutput(BaseModel):
    """Выход RAG-системы для одного вопроса."""

    generated_answer: str = Field(..., description="Сгенерированный ответ")
    rewritten_query: str = Field(default="", description="Переписанный запрос")
    retrieved_contexts: list[RetrievedContext] = Field(
        default_factory=list, description="Найденные документы"
    )
    footnotes: list[Footnote] = Field(default_factory=list, description="Сноски для UI")
    latency_sec: float = Field(default=0.0, description="Общее время pipeline")
    answer_type: str = Field(default="final_answer", description="Тип ответа")

    trace: list[TraceStep] = Field(default_factory=list, description="Трассировка шагов агента")

    timings: dict[str, float] | None = Field(
        default=None, description="Детальные таймеры по этапам pipeline"
    )
    ragas_scores: dict[str, float] | None = Field(
        default=None, description="Оценки RAGAS для этого ответа"
    )


class EvaluationResult(BaseModel):
    """Полный результат оценки одного вопроса."""

    id: str = Field(..., description="ID вопроса")
    question: str = Field(..., description="Вопрос")
    expected_answer: str | list[str] = Field(..., description="Эталонный ответ")
    source_file: str = Field(default="", description="Исходный файл")
    difficulty: str = Field(default="", description="Сложность")
    category: str = Field(default="", description="Категория")

    rag_output: RAGOutput | None = Field(default=None, description="Результат RAG")

    ragas_scores: dict[str, float] | None = Field(default=None, description="Оценки RAGAS")

    error: str | None = Field(default=None, description="Ошибка, если была")

    keywords: list[str] = Field(
        default_factory=list,
        description="Ключевые слова для проверки качества ответа",
    )
    meta: dict = Field(
        default_factory=dict, description="Дополнительные метаданные (expected_tools, context)"
    )


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
