import pytest

from src.application.services.citation_formatter import CitationFootnoteBuilder
from src.application.services.citation_verifier import CitationVerifier


class TestCitationVerifier:
    """Tests for the CitationVerifier service."""

    @pytest.fixture
    def verifier(self):
        return CitationVerifier()

    def test_extract_prose_sentences(self, verifier):
        text = """# Header
This is a valid sentence.
```python
print("this is code")
```
Another valid sentence here.
**Key:** Value
- List item 1
Short."""
        sentences = verifier._extract_prose_sentences(text)
        assert len(sentences) == 3
        assert "This is a valid sentence." in sentences
        assert "Another valid sentence here." in sentences


    def test_verify_citations(self, verifier):
        answer = "Согласно [1], все работает. Но [99] - это галлюцинация. [2] тоже полезен."
        report = verifier.verify(answer, context_doc_count=5)

        assert report.valid_citations == [1, 2]
        assert report.invalid_citations == [99]
        assert report.uncited_docs == [3, 4, 5]
        # Sentences: "Согласно [1], все работает.",
        # "Но [99] - это галлюцинация.", "[2] тоже полезен."
        # All 3 have citations. Coverage = 1.0
        assert report.citation_coverage == 1.0

    def test_clean_invalid_citations(self, verifier):
        answer = "Valid [1] and invalid [99]."
        cleaned = verifier.clean_invalid_citations(answer, context_doc_count=5)
        assert cleaned == "Valid [1] and invalid ."

class TestCitationFootnoteBuilder:
    """Tests for the CitationFootnoteBuilder service."""

    @pytest.fixture
    def builder(self):
        return CitationFootnoteBuilder()

    def test_build_footnotes_mixed_sources(self, builder):
        answer = "Sources [1] and [2] are used."
        registry = [
            {
                "source_type": "doc",
                "source_name": "local.md",
                "quote_preview": "some quote",
                "service": "nginx",
                "header_path": "Root > Section"
            },
            {
                "source_type": "web",
                "title": "Web Page",
                "source_name": "example.com",
                "url": "https://example.com",
                "quote_preview": "web quote"
            },
            {
                "source_type": "doc",
                "source_name": "unused.md"
            }
        ]

        footnotes = builder.build_footnotes(answer, registry)

        assert len(footnotes) == 2

        # Check first footnote (doc)
        f1 = footnotes[0]
        assert f1.id == 1
        assert f1.source_type == "doc"
        assert f1.title == "local.md"
        assert f1.service == "nginx"

        # Check second footnote (web)
        f2 = footnotes[1]
        assert f2.id == 2
        assert f2.source_type == "web"
        assert f2.title == "Web Page"
        assert f2.url == "https://example.com"
