from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.dto.requests import ChatRequest
from src.application.services.rag_service import RAGService
from src.domain.models.query import QueryExpansion


@pytest.fixture
def mock_llm():
    return MagicMock()

@pytest.fixture
def mock_search_engine():
    engine = MagicMock()
    engine.retrieve_candidates = AsyncMock(return_value={
        "doc1": {"raw_content": "nginx info", "score": 0.9, "rrf_score": 0.5}
    })
    engine.rerank_candidates = MagicMock(return_value=[
        {"raw_content": "nginx info", "score": 0.9}
    ])
    return engine

@pytest.fixture
def rag_service(mock_llm, mock_search_engine):
    service = RAGService(llm_client=mock_llm, search_engine=mock_search_engine)
    # Mock internal components to simplify testing main flow
    service.query_expander = MagicMock()
    service.query_expander.expand = AsyncMock(return_value=QueryExpansion(
        rewritten_query="rewritten query",
        variations=["v1", "v2"]
    ))
    service.query_expander.get_all_queries = MagicMock(return_value=["rewritten query", "v1", "v2"])

    service.document_analyzer = MagicMock()
    service.document_analyzer.analyze_batch = AsyncMock(return_value=[
        {"raw_content": "nginx info", "relevance_score": 5, "summary_content": "nginx info"}
    ])

    service.answer_generator = MagicMock()
    service.answer_generator.generate_answer = AsyncMock(return_value="Final Answer")

    service.citation_verifier = MagicMock()
    service.citation_verifier.verify = MagicMock(return_value=MagicMock(invalid_citations=[]))

    return service

@pytest.mark.asyncio
async def test_process_query_standard_flow(rag_service, mock_search_engine):
    request = ChatRequest(query="install nginx", history=[])

    response = await rag_service.process_query(request)

    assert response.answer == "Final Answer"
    assert response.answer_type == "final_answer"
    assert response.rewritten_query == "rewritten query"
    assert len(response.sources) == 1

    # Verify calls
    rag_service.query_expander.expand.assert_called_once()
    mock_search_engine.retrieve_candidates.assert_called()
    rag_service.answer_generator.generate_answer.assert_called_once()

@pytest.mark.asyncio
async def test_process_query_no_docs(rag_service, mock_search_engine):
    # Setup nothing retrieved
    mock_search_engine.retrieve_candidates = AsyncMock(return_value={})

    # Or explicitly document analyzer returns empty
    rag_service.document_analyzer.analyze_batch = AsyncMock(return_value=[])

    # Mock clarifying generation
    rag_service.answer_generator.generate_clarifying_question = AsyncMock(return_value="Clarify?")

    request = ChatRequest(query="random query", history=[])
    response = await rag_service.process_query(request)

    assert response.answer_type == "clarifying_question"
    assert response.answer == "Clarify?"

@pytest.mark.asyncio
async def test_process_query_stream(rag_service):
    request = ChatRequest(query="stream query", history=[])

    # Mock answer generator for stream
    # process_query_stream now calls generate_answer (sync logic fake stream)
    rag_service.answer_generator.generate_answer = AsyncMock(return_value="Full Answer")

    chunks = []
    async for chunk in rag_service.process_query_stream(request):
        chunks.append(chunk)

    assert "Full Answer" in chunks
    # Sources should be appended at the end
    assert any("[SOURCES]" in c for c in chunks)

