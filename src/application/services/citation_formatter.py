"""Сервис форматирования цитат.

Генерирует footnotes для UI — список ссылок на источники.
"""

import re

from src.application.dto.responses import Footnote
from src.domain.models.response import SourceDoc


class CitationFootnoteBuilder:
    """Создаёт footnotes из ответа и источников.

    Извлекает использованные [doc:X] из ответа и формирует
    список Footnote объектов для отображения в UI.
    """

    CITATION_PATTERN = re.compile(r"\[doc:(\d+)\]")

    def build_footnotes(
        self,
        answer: str,
        sources: list[SourceDoc],
    ) -> list[Footnote]:
        """Создаёт footnotes для использованных цитат.

        Args:
            answer: Ответ с [doc:X] цитатами.
            sources: Список источников (SourceDoc).

        Returns:
            Список Footnote для UI (только использованные doc IDs).

        """
        cited_ids = {int(m) for m in self.CITATION_PATTERN.findall(answer)}

        source_map = {s.doc_id: s for s in sources}

        footnotes = []
        for doc_id in sorted(cited_ids):
            if doc_id in source_map:
                source = source_map[doc_id]
                footnotes.append(
                    Footnote(
                        doc_id=doc_id,
                        service=source.service,
                        title=source.header_path or source.source_file,
                        source_file=source.source_file,
                        quote=source.content,
                    )
                )

        return footnotes
