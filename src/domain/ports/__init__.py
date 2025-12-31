"""Ports — абстракции для Dependency Inversion.

Содержит Protocol интерфейсы:
- llm.py — LLMPort (абстракция LLM-клиента)
- vector_store.py — VectorStorePort (абстракция векторного хранилища)
- document_store.py — DocumentStorePort (абстракция документного хранилища)

Adapters (реализации) находятся в infrastructure/.
"""

from src.domain.ports.document_store import DocumentStorePort
from src.domain.ports.llm import LLMPort
from src.domain.ports.vector_store import VectorStorePort

__all__ = [
    "LLMPort",
    "VectorStorePort",
    "DocumentStorePort",
]
