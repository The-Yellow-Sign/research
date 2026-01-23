"""Сервис форматирования цитат.

Генерирует footnotes для UI — список ссылок на источники.
Поддерживает doc (локальные) и web источники.
"""

import re
from typing import Any

from src.application.dto.responses import Footnote


class CitationFootnoteBuilder:
    """Создаёт footnotes из ответа и реестра источников.

    Извлекает использованные [N] из ответа и формирует
    список Footnote объектов для отображения в UI.
    """

    CITATION_PATTERN = re.compile(r"\[(\d+)\]")

    def build_footnotes(
        self,
        answer: str,
        sources_registry: list[dict[str, Any]],
    ) -> list[Footnote]:
        """Создаёт footnotes для использованных цитат.

        Args:
            answer: Ответ с [1], [2] цитатами.
            sources_registry: Единый реестр источников (doc + web).

        Returns:
            Список Footnote для UI (только использованные IDs).

        """
        cited_ids = {int(m) for m in self.CITATION_PATTERN.findall(answer)}

        footnotes = []
        for source_id in sorted(cited_ids):
            idx = source_id - 1
            if 0 <= idx < len(sources_registry):
                source = sources_registry[idx]
                source_type = source.get("source_type", "doc")

                if source_type == "doc":
                    footnotes.append(
                        Footnote(
                            id=source_id,
                            source_type="doc",
                            title=source.get("source_name", source.get("source", "")),
                            source=source.get("source_name", source.get("source", "")),
                            quote=source.get("quote_preview", "")[:200],
                            service=source.get("service"),
                            header_path=source.get("header_path"),
                        )
                    )
                else:
                    footnotes.append(
                        Footnote(
                            id=source_id,
                            source_type="web",
                            title=source.get("title", source.get("source_name", "")),
                            source=source.get("source_name", ""),
                            quote=source.get("quote_preview", "")[:200],
                            url=source.get("url"),
                        )
                    )

        return footnotes
