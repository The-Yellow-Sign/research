import pytest
from pydantic import ValidationError

from src.domain.models.query import DocAnalysis, QueryExpansion
from src.domain.models.response import SourceDoc


def test_query_expansion_valid():
    expansion = QueryExpansion(
        rewritten_query="how to install nginx",
        variations=["nginx installation guide", "setup nginx on ubuntu"]
    )
    assert expansion.rewritten_query == "how to install nginx"
    assert len(expansion.variations) == 2

def test_query_expansion_invalid_variations_count():
    with pytest.raises(ValidationError):
        # too few variations (min_length=2)
        QueryExpansion(
            rewritten_query="test",
            variations=["one"]
        )

def test_doc_analysis_valid():
    analysis = DocAnalysis(
        relevance_score=5,
        summary="This is a great doc.",
        reasoning="It directly answers the question."
    )
    assert analysis.relevance_score == 5

def test_doc_analysis_invalid_score():
    with pytest.raises(ValidationError):
        # score out of range (0-5)
        DocAnalysis(
            relevance_score=10,
            summary="test",
            reasoning="test"
        )

def test_source_doc_valid():
    doc = SourceDoc(
        doc_id=1,
        rank=1,
        score=0.95,
        service="nginx",
        source_file="nginx.md",
        header_path="Installation > Ubuntu",
        content="apt-get install nginx"
    )
    assert doc.doc_id == 1
    assert doc.service == "nginx"
