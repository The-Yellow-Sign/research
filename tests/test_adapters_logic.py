import pytest

from src.infrastructure.nlp.metadata_extractor import GLiNERExtractor


@pytest.fixture
def extractor():
    return GLiNERExtractor()

def test_extract_regex_version(extractor):
    text = "Using version 1.2.3 and v2.0"
    result = extractor._extract_regex(text)
    assert "version" in result
    assert "1.2.3" in result["version"]
    assert "2.0" in result["version"]

def test_extract_regex_port(extractor):
    text = "Listening on port 8080 or :443"
    result = extractor._extract_regex(text)
    assert "port" in result
    assert "8080" in result["port"]
    assert "443" in result["port"]

def test_extract_regex_environment(extractor):
    text = "Deployment for Production and staging"
    result = extractor._extract_regex(text)
    assert "environment" in result
    assert "production" in result["environment"]
    assert "staging" in result["environment"]

def test_extract_regex_k8s_kind(extractor):
    text = "kind: Deployment and kind: Service"
    result = extractor._extract_regex(text)
    assert "k8s_kind" in result
    assert "Deployment" in result["k8s_kind"]
    assert "Service" in result["k8s_kind"]

def test_extract_metadata_combined(extractor, monkeypatch):
    # Mock gliner to avoid model loading
    monkeypatch.setattr(
        extractor,
        "_extract_gliner",
        lambda text, labels, threshold: {"gliner_label": ["gliner_val"]},
    )

    text = "version 1.0"
    result = extractor.extract_metadata(text)

    assert "gliner_label" in result
    assert "version" in result
    assert "1.0" in result["version"]
