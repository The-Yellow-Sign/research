"""Сервис верификации цитат в LLM ответах.

Проверяет корректность [doc:X] ссылок и удаляет галлюцинированные.
"""

import re
from dataclasses import dataclass


@dataclass
class CitationReport:
    """Результат верификации цитат.

    Attributes:
        valid_citations: Список doc IDs, присутствующих в контексте.
        invalid_citations: Список doc IDs, отсутствующих в контексте (галлюцинации).
        uncited_docs: Список doc IDs, не упомянутых в ответе.
        citation_coverage: Доля предложений с цитатами (0.0-1.0).

    """

    valid_citations: list[int]
    invalid_citations: list[int]
    uncited_docs: list[int]
    citation_coverage: float


class CitationVerifier:
    """Верификатор [doc:X] ссылок в LLM ответах.

    Проверяет что все цитаты в ответе соответствуют реальным документам
    из контекста. Может очищать ответ от невалидных ссылок.
    """

    CITATION_PATTERN = re.compile(r"\[doc:(\d+)\]")

    def _extract_prose_sentences(self, text: str) -> list[str]:
        """Извлекает реальные предложения из markdown-текста.

        Исключает code blocks, заголовки и короткие фрагменты.

        Args:
            text: Markdown-текст ответа.

        Returns:
            Список реальных предложений для анализа coverage.

        """
        cleaned = re.sub(r"```[\s\S]*?```", "", text)
        cleaned = re.sub(r"`[^`]+`", "", cleaned)

        cleaned = re.sub(r"\*\*[^*]+:\*\*", "", cleaned)
        cleaned = re.sub(r"#{1,6}\s+[^\n]+", "", cleaned)

        cleaned = re.sub(r"^\s*\d+\.\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*[-*]\s*", "", cleaned, flags=re.MULTILINE)

        raw_sentences = re.split(r"(?<=[.!?])\s+", cleaned)

        sentences = []
        for s in raw_sentences:
            s = s.strip()
            if len(s) >= 20 and re.search(r"[а-яА-Яa-zA-Z]{3,}", s):
                sentences.append(s)

        return sentences

    def verify(
        self,
        answer: str,
        context_doc_count: int,
    ) -> CitationReport:
        """Проверяет валидность всех [doc:X] в ответе.

        Args:
            answer: Сгенерированный LLM ответ с [doc:X] ссылками.
            context_doc_count: Количество документов в контексте (N).
                               Валидные ID: 1..N.

        Returns:
            CitationReport с результатами верификации.

        """
        valid_ids = set(range(1, context_doc_count + 1))
        cited_ids = {int(m) for m in self.CITATION_PATTERN.findall(answer)}

        valid_citations = sorted(cited_ids & valid_ids)
        invalid_citations = sorted(cited_ids - valid_ids)
        uncited_docs = sorted(valid_ids - cited_ids)

        sentences = self._extract_prose_sentences(answer)
        if sentences:
            cited_sentences = sum(
                1 for s in sentences if self.CITATION_PATTERN.search(s)
            )
            coverage = cited_sentences / len(sentences)
        else:
            coverage = 0.0

        return CitationReport(
            valid_citations=valid_citations,
            invalid_citations=invalid_citations,
            uncited_docs=uncited_docs,
            citation_coverage=round(coverage, 3),
        )

    def clean_invalid_citations(
        self,
        answer: str,
        context_doc_count: int,
    ) -> str:
        """Удаляет невалидные [doc:X] ссылки из ответа.

        Args:
            answer: Ответ с потенциально невалидными ссылками.
            context_doc_count: Количество документов в контексте.

        Returns:
            Очищенный ответ без галлюцинированных ссылок.

        """
        valid_ids = set(range(1, context_doc_count + 1))

        def replacer(match: re.Match) -> str:
            doc_id = int(match.group(1))
            return match.group(0) if doc_id in valid_ids else ""

        cleaned = self.CITATION_PATTERN.sub(replacer, answer)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return cleaned.strip()
