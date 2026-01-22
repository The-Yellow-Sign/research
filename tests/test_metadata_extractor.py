from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.nlp.metadata_extractor import GLiNERExtractor


@pytest.fixture
def mock_gliner_class():
    with patch("src.infrastructure.nlp.metadata_extractor.GLiNER") as mock_cls:
        # Also patch the availability flag
        with patch("src.infrastructure.nlp.metadata_extractor._GLINER_AVAILABLE", True):
            yield mock_cls

@pytest.fixture
def extractor(mock_gliner_class):
    return GLiNERExtractor()

def test_gliner_lazy_load(extractor, mock_gliner_class):
    # Model shouldn't be loaded on init
    assert extractor._model is None
    mock_gliner_class.from_pretrained.assert_not_called()

    # Accessing _get_model should trigger load
    extractor._get_model()
    mock_gliner_class.from_pretrained.assert_called_once()
    assert extractor._model is not None

def test_extract_gliner_success(extractor, mock_gliner_class):
    # Setup mock model prediction
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model # Fix: .to() should return self
    mock_model.predict_entities.return_value = [
        {"label": "service", "text": "nginx"},
        {"label": "version", "text": "1.21"}
    ]
    mock_gliner_class.from_pretrained.return_value = mock_model

    result = extractor.extract_metadata("nginx 1.21")

    assert "service" in result
    assert "nginx" in result["service"]
    assert "version" in result
    assert "1.21" in result["version"]

def test_extract_regex_fallback(extractor, mock_gliner_class):
    # Force _get_model to return None (simulate load failure or missing lib)
    # But usually extract_metadata calls _extract_gliner which calls _get_model.
    # If we want to test purely fallback logic when GLiNER returns empty or fails:

    mock_model = MagicMock()
    # Return empty list from gliner
    mock_model.predict_entities.return_value = []
    mock_gliner_class.from_pretrained.return_value = mock_model

    # Text contains clear regex patterns
    text = "version: v1.0.0"

    result = extractor.extract_metadata(text)

    # Should rely on regex
    assert "version" in result
    assert "1.0.0" in result["version"]
