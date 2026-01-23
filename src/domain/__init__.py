"""Domain Layer — ядро бизнес-логики.

Содержит:
- models/ — доменные модели (Value Objects, Entities)
- services/ — доменные сервисы (чистая бизнес-логика)
- ports/ — абстракции (Protocol интерфейсы для Dependency Inversion)

Этот слой НЕ зависит от infrastructure или interfaces.
"""

from src.domain.models import (
    DocAnalysis,
    ExtractedBlock,
    QueryExpansion,
    SourceDoc,
    generate_parent_id,
)
from src.domain.ports import (
    DocumentStorePort,
    LLMPort,
    MetadataExtractorPort,
    VectorStorePort,
)
from src.domain.services import (
    build_header_path,
    build_vector_text,
    infer_service_from_path,
    parse_frontmatter,
    process_markdown_ast,
)

__all__ = [
    "ExtractedBlock",
    "generate_parent_id",
    "QueryExpansion",
    "DocAnalysis",
    "SourceDoc",
    "parse_frontmatter",
    "infer_service_from_path",
    "build_header_path",
    "process_markdown_ast",
    "build_vector_text",
    "LLMPort",
    "VectorStorePort",
    "DocumentStorePort",
    "MetadataExtractorPort",
]
