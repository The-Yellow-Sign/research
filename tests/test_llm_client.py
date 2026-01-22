from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from src.infrastructure.llm.client import LLMClient


class MockResponse(BaseModel):
    """Mock Pydantic model for LLM response testing."""

    result: str

@pytest.fixture
def llm_client():
    client = AsyncMock()
    return LLMClient(client=client, model="test-model")

@pytest.mark.asyncio
async def test_generate(llm_client):
    # Setup
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Generated text"

    llm_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

    # Act
    result = await llm_client.generate("prompt")

    # Assert
    assert result == "Generated text"
    llm_client.client.chat.completions.create.assert_called_once()
    args = llm_client.client.chat.completions.create.call_args[1]
    assert args["messages"][0]["content"] == "prompt"

@pytest.mark.asyncio
async def test_generate_structured(llm_client):
    # Setup
    mock_parsed = MockResponse(result="structured")
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.parsed = mock_parsed

    llm_client.client.chat.completions.parse = AsyncMock(return_value=mock_response)

    # Act
    result = await llm_client.generate_structured(
        messages=[{"role": "user", "content": "hi"}],
        response_model=MockResponse
    )

    # Assert
    assert result.result == "structured"
    assert isinstance(result, MockResponse)
    llm_client.client.chat.completions.parse.assert_called_once()

@pytest.mark.asyncio
async def test_check_health(llm_client):
    llm_client.client.models.list = AsyncMock(return_value="ok")
    assert await llm_client.check_health() is True

    llm_client.client.models.list = AsyncMock(side_effect=Exception("error"))
    assert await llm_client.check_health() is False
