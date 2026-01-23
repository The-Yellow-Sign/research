import unittest
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.application.dto.responses import ChatResponse
from src.application.services.rag_service import RAGService
from src.application.use_cases.agent_controller import AgentController
from src.application.use_cases.agent_models import AgentEvent, AgentEventType, AgentResponse
from src.interfaces.api.app import app


@pytest.fixture
def mock_rag_service():
    service = MagicMock(spec=RAGService)
    service.process_query = AsyncMock(return_value=ChatResponse(
        answer_type="final_answer",
        answer="Test answer",
        sources=[],
        rewritten_query="test query",
        trace={"trace_id": "test-trace"}
    ))
    service.llm_client = MagicMock()
    service.llm_client.check_health = AsyncMock(return_value=True)
    return service

@pytest.fixture
def mock_agent_controller():
    controller = MagicMock(spec=AgentController)
    # AgentResponse is a dataclass
    controller.run = AsyncMock(return_value=AgentResponse(
        answer="Agent answer",
        sources=[],
        steps=1,
        total_time_sec=1.0,
        trace={"step1": "done"}
    ))

    # Mock stream
    async def mock_stream_gen(*args, **kwargs):
        # Yield an AgentEvent
        yield AgentEvent(
            type=AgentEventType.ANSWER,
            content="Stream chunk"
        )
    controller.run_stream = mock_stream_gen

    return controller

@pytest.fixture
def client(mock_rag_service, mock_agent_controller):
    # Patch dependencies used in lifespan
    with unittest.mock.patch("src.interfaces.api.app.SearchEngine") as MockSearchEngine, \
         unittest.mock.patch("src.interfaces.api.app.LLMClient"), \
         unittest.mock.patch("src.interfaces.api.app.RAGService") as MockRAGService, \
         unittest.mock.patch("src.interfaces.api.app.create_default_tools"), \
         unittest.mock.patch("src.interfaces.api.app.AgentController") as MockAgentControllerClass:

        # Setup mocks
        mock_search_instance = MockSearchEngine.return_value
        mock_search_instance.opensearch_client = MagicMock()
        mock_search_instance.opensearch_client.info = MagicMock()
        mock_search_instance.milvus_collection = MagicMock()
        mock_search_instance.milvus_collection.num_entities = 100

        MockRAGService.return_value = mock_rag_service
        MockAgentControllerClass.return_value = mock_agent_controller

        with TestClient(app) as c:
            # We also need to ensure app.state is set correctly if lifespan ran,
            # but since we patched the classes, lifespan should use our mocks.
             yield c

def test_health_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_health_ready(client):
    # Depending on how the client handles async endpoint calls internally,
    # TestClient usually wraps them synchronously.
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["opensearch"] is True
    assert data["checks"]["milvus"] is True
    assert data["checks"]["llm"] is True

def test_chat_endpoint(client, mock_rag_service):
    payload = {"query": "test query", "history": []}
    response = client.post("/chat", json=payload)
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Test answer"
    mock_rag_service.process_query.assert_called_once()

def test_agent_chat_endpoint(client, mock_agent_controller):
    payload = {"query": "agent query", "history": []}
    response = client.post("/agent/chat", json=payload)
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Agent answer"
    mock_agent_controller.run.assert_called_once()

def test_agent_chat_stream_endpoint(client, mock_agent_controller):
    payload = {"query": "stream query", "history": []}
    with client.stream("POST", "/agent/chat/stream", json=payload) as response:
        assert response.status_code == 200
        # Check if we get some data events
        lines = list(response.iter_lines())
        assert len(lines) > 0
        # Should contain "data:"
        assert any("data:" in line for line in lines)
        assert any("Stream chunk" in line for line in lines)
