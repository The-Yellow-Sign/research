import time
from unittest.mock import MagicMock

import pytest

from src.application.use_cases.agent_controller import AgentController
from src.application.use_cases.agent_models import AgentResponse
from src.application.use_cases.observation_manager import ObservationManager


@pytest.fixture
def mock_llm():
    return MagicMock()

@pytest.fixture
def controller(mock_llm):
    return AgentController(llm=mock_llm, tools=[])

def test_reindex_citations_simple(controller):
    text = "Based on [1] and [2], we should do X."
    offset = 5
    expected = "Based on [6] and [7], we should do X."
    assert controller._reindex_citations(text, offset) == expected

def test_reindex_citations_no_citations(controller):
    text = "No citations here."
    assert controller._reindex_citations(text, 10) == text

def test_reindex_citations_multiple_digits(controller):
    text = "Source [10] is relevant."
    assert controller._reindex_citations(text, 5) == "Source [15] is relevant."

def test_build_response_basic(controller):
    answer = "The answer is 42."
    sources = ["source1"]
    step = 3
    start_time = time.perf_counter() - 1.0 # 1 second ago

    response = controller._build_response(answer, sources, step, start_time)

    assert isinstance(response, AgentResponse)
    assert response.answer == answer
    assert response.sources == sources
    assert response.steps == step
    assert response.total_time_sec >= 1.0
    assert response.footnotes == []
    assert response.citation_metrics is None

def test_build_dynamic_hints_no_hints(controller):
    obs = ObservationManager(max_tokens=1000)
    assert controller._build_dynamic_hints(obs) == ""

def test_build_dynamic_hints_empty_results(controller):
    obs = ObservationManager(max_tokens=1000)
    obs.add("результатов: 0", priority=2)
    obs.add("результатов: 0", priority=2)
    hints = controller._build_dynamic_hints(obs)
    assert "⚠️ Предыдущие поиски в rag_search были пустыми" in hints

def test_build_dynamic_hints_errors(controller):
    obs = ObservationManager(max_tokens=1000)
    obs.add("ОШИБКА: timeout", priority=3)
    hints = controller._build_dynamic_hints(obs)
    assert "⚠️ Были ошибки инструментов" in hints
