from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.query_decomposer import (
    DecomposedQuery,
    DecompositionResponse,
    QueryDecomposer,
)
from src.domain.ports.llm import LLMPort


@pytest.fixture
def mock_llm():
    return MagicMock(spec=LLMPort)

@pytest.fixture
def decomposer(mock_llm):
    return QueryDecomposer(llm=mock_llm)

@pytest.mark.asyncio
async def test_decompose_basic(decomposer, mock_llm):
    query = "how to setup nginx"
    expected_queries = ["nginx installation", "nginx configuration"]

    # Mock structured response
    mock_response = MagicMock(spec=DecompositionResponse)
    mock_response.queries = expected_queries
    mock_llm.generate_structured = AsyncMock(return_value=mock_response)

    result = await decomposer.decompose(query)

    assert isinstance(result, DecomposedQuery)
    assert result.original == query
    assert result.expanded_queries == expected_queries
    mock_llm.generate_structured.assert_called_once()


@pytest.mark.asyncio
async def test_decompose_cache_hit(decomposer, mock_llm):
    query = "how to setup nginx"
    expected_queries = ["nginx installation"]

    mock_response = MagicMock(spec=DecompositionResponse)
    mock_response.queries = expected_queries
    mock_llm.generate_structured = AsyncMock(return_value=mock_response)

    # First call
    await decomposer.decompose(query)
    # Second call
    result = await decomposer.decompose(query)

    assert result.expanded_queries == expected_queries
    # Should be called only once due to cache
    assert mock_llm.generate_structured.call_count == 1

@pytest.mark.asyncio
async def test_decompose_cache_with_history(decomposer, mock_llm):
    query = "tell me more"
    history = [{"role": "user", "content": "setup nginx"}]

    mock_response = MagicMock(spec=DecompositionResponse)
    mock_response.queries = ["details"]
    mock_llm.generate_structured = AsyncMock(return_value=mock_response)

    # First call
    await decomposer.decompose(query, history=history)
    # Second call with same history
    await decomposer.decompose(query, history=history)

    assert mock_llm.generate_structured.call_count == 1

    # Third call with different history
    different_history = [{"role": "user", "content": "setup postgres"}]
    mock_response_2 = MagicMock(spec=DecompositionResponse)
    mock_response_2.queries = ["postgres details"]
    # We set side_effect to return different values sequentially if needed,
    # but here we can just update return_value or use side_effect for multiple calls
    mock_llm.generate_structured.side_effect = [mock_response, mock_response, mock_response_2]
    # Reset mock to count logic easier or just check total count
    mock_llm.generate_structured.reset_mock()
    mock_llm.generate_structured.return_value = mock_response_2

    await decomposer.decompose(query, history=different_history)

    assert mock_llm.generate_structured.call_count == 1  # 1 new call for new history


@pytest.mark.asyncio
async def test_decompose_error_fallback(decomposer, mock_llm):
    query = "risky query"
    mock_llm.generate_structured = AsyncMock(side_effect=Exception("LLM down"))

    result = await decomposer.decompose(query)

    assert result.original == query
    assert result.expanded_queries == [query]

