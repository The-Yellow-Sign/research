from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.tools.tool_base import ToolResult
from src.application.use_cases.agent_controller import AgentController
from src.application.use_cases.agent_models import (
    AgentAction,
    AgentDecision,
    AgentResponse,
)


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    # No client needed
    return llm

@pytest.fixture
def mock_tool():
    tool = MagicMock()
    tool.name = "rag_search"
    tool.execute = AsyncMock(
        return_value=ToolResult(
            success=True, data="Search result content", metadata={"documents": []}
        )
    )
    return tool

@pytest.mark.asyncio
async def test_agent_complete_flow_mocked(mock_llm, mock_tool):
    controller = AgentController(llm=mock_llm, tools=[mock_tool])

    # Mock Decomposer
    controller.decomposer.decompose = AsyncMock(return_value=MagicMock(expanded_queries=["query"]))

    # Mock LLM calls (Structured Output via .parse)
    # Step 1: Decision to search
    decision1 = AgentDecision(
        thought="I need to search for nginx.",
        tool_name=AgentAction.RAG_SEARCH,
        params={"query": "nginx installation"}
    )

    # Step 2: Final answer
    decision2 = AgentDecision(
        thought="I found the info, now answering.",
        tool_name=AgentAction.FINAL_ANSWER,
        params={"answer": "To install nginx, use apt install nginx.", "sources": ["doc:1"]}
    )

    # New: Mock generate_structured to return decision directly
    mock_llm.generate_structured = AsyncMock(side_effect=[decision1, decision2])

    # Run
    response = await controller.run("how to install nginx")

    # Verify
    assert isinstance(response, AgentResponse)
    assert "apt install nginx" in response.answer
    assert response.steps == 2
    # 2 calls: one from _prefetch_expanded_queries, and one from the first ReAct step
    assert mock_tool.execute.call_count == 2
    assert mock_llm.generate_structured.call_count == 2


@pytest.mark.asyncio
async def test_agent_max_iterations_fallback(mock_llm):
    # Mock LLM to always want to search, never giving final answer
    controller = AgentController(llm=mock_llm, tools=[MagicMock(name="rag_search")])
    controller.decomposer.decompose = AsyncMock(return_value=MagicMock(expanded_queries=[]))

    decision = AgentDecision(
        thought="I want to search again...",
        tool_name=AgentAction.RAG_SEARCH,
        params={"query": "more search"}
    )

    mock_llm.generate_structured = AsyncMock(return_value=decision)

    # Run with small iterations limit for speed if possible,
    # but here it uses settings.agent_max_iterations
    # We'll just verify it returns something after it hits the limit

    from src.config import settings
    max_steps = settings.agent_max_iterations

    response = await controller.run("never ending story")

    assert "Не удалось найти ответ" in response.answer
    assert response.steps == max_steps

