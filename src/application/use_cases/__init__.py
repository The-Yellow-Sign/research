"""Use Cases — сценарии использования.

Содержит Application Services:
- query_processor.py — главный оркестратор RAG-пайплайна
- query_expander.py — расширение запросов
- document_analyzer.py — LLM-анализ релевантности документов
"""

from src.application.use_cases.document_analyzer import DocumentAnalyzer
from src.application.use_cases.query_expander import QueryExpander

__all__ = [
    "QueryExpander",
    "DocumentAnalyzer",
]
