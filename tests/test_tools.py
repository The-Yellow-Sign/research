from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.tools.rag_search import RagSearchTool
from src.application.tools.verify_answer import VerifyAnswerTool
from src.application.tools.web_search import WebSearchTool
from src.domain.ports.search_engine import SearchEnginePort


@pytest.fixture
def mock_search_engine():
    return MagicMock(spec=SearchEnginePort)

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.client = MagicMock()
    llm.client.chat.completions.create = AsyncMock()
    return llm

@pytest.mark.asyncio
async def test_rag_search_tool_success(mock_search_engine):
    tool = RagSearchTool(search_engine=mock_search_engine)
    query = "nginx"

    mock_search_engine.retrieve_candidates = AsyncMock(
        return_value={"1": {"raw_content": "nginx content"}}
    )
    mock_search_engine.rerank_candidates = MagicMock(
        return_value=[
            {"raw_content": "nginx content", "source": "nginx.md", "score": 0.9}
        ]
    )

    result = await tool.execute(query=query)

    assert result.success is True
    assert "nginx content" in result.data
    assert result.metadata["source_type"] == "doc"

@pytest.mark.asyncio
async def test_rag_search_tool_no_results(mock_search_engine):
    tool = RagSearchTool(search_engine=mock_search_engine)
    mock_search_engine.retrieve_candidates = AsyncMock(return_value={})

    result = await tool.execute(query="unknown")

    assert result.success is True
    assert "Документы не найдены" in result.data

@pytest.mark.asyncio
async def test_web_search_tool_no_api_key():
    tool = WebSearchTool(api_key="temporary")
    tool.api_key = "" # Force empty to skip fallback in __init__
    result = await tool.execute(query="test")
    assert result.success is False
    assert "TAVILY_API_KEY не настроен" in result.error

@pytest.mark.asyncio
async def test_verify_answer_tool_success(mock_llm):
    tool = VerifyAnswerTool(llm=mock_llm)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"valid": true, "reason": "Consistent with context"}'
    )
    mock_llm.client.chat.completions.create.return_value = mock_response

    result = await tool.execute(answer="The sky is blue.", context="The sky is blue.")

    assert result.success is True
    assert "valid" in result.data
    mock_llm.client.chat.completions.create.assert_called_once()
