from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.agent_controller import AgentController
from src.application.use_cases.agent_models import AgentReflection
from src.domain.ports.llm import LLMPort


@pytest.fixture
def mock_llm():
    return MagicMock(spec=LLMPort)

@pytest.fixture
def mock_tools():
    return {}

@pytest.fixture
def controller(mock_llm, mock_tools):
    return AgentController(llm=mock_llm, tools=mock_tools)

@pytest.mark.asyncio
async def test_reflection_approved(controller, mock_llm):
    # Setup
    query = "test query"
    candidate_answer = "perfect answer"
    observations = ["obs1"]

    # Mock LLM response
    mock_reflection = AgentReflection(
        is_approved=True,
        thought="The answer is complete and accurate.",
        critique=""
    )
    mock_llm.generate_structured = AsyncMock(return_value=mock_reflection)

    # Execute
    is_approved, result = await controller._reflect_on_answer(query, candidate_answer, observations)

    # Verify
    assert is_approved is True
    assert result == candidate_answer
    mock_llm.generate_structured.assert_called_once()

@pytest.mark.asyncio
async def test_reflection_rejected(controller, mock_llm):
    # Setup
    query = "test query"
    candidate_answer = "bad answer"
    observations = ["obs1"]
    critique_text = "Missing step 3."

    # Mock LLM response
    mock_reflection = AgentReflection(
        is_approved=False,
        thought="User missed a crucial step.",
        critique=critique_text
    )
    mock_llm.generate_structured = AsyncMock(return_value=mock_reflection)

    # Execute
    is_approved, result = await controller._reflect_on_answer(query, candidate_answer, observations)

    # Verify
    assert is_approved is False
    assert result == critique_text
