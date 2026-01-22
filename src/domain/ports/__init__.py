"""Ports — абстракции для Dependency Inversion.

Содержит Protocol интерфейсы:
- llm.py — LLMPort (абстракция LLM-клиента)
- vector_store.py — VectorStorePort (абстракция векторного хранилища)
- document_store.py — DocumentStorePort (абстракция документного хранилища)
- search_engine.py — SearchEnginePort (абстракция поискового движка)

Adapters (реализации) находятся в infrastructure/.
"""

from src.domain.ports.document_store import DocumentStorePort
from src.domain.ports.llm import LLMPort
from src.domain.ports.metadata_extractor import MetadataExtractorPort
from src.domain.ports.search_engine import SearchEnginePort
from src.domain.ports.vector_store import VectorStorePort

__all__ = [
    "LLMPort",
    "VectorStorePort",
    "DocumentStorePort",
    "MetadataExtractorPort",
    "SearchEnginePort",
]
