"""Session Store — хранение истории диалогов.

In-memory хранилище для conversation memory.
"""

import time
from dataclasses import dataclass, field
from typing import ClassVar

from src.config import settings


@dataclass
class Message:
    """Сообщение в диалоге."""

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    """Сессия диалога."""

    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    max_messages: int = 10

    def add_message(self, role: str, content: str) -> None:
        """Добавляет сообщение в сессию."""
        self.messages.append(Message(role=role, content=content))
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def get_history(self) -> list[dict[str, str]]:
        """Возвращает историю в формате для LLM."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def get_context_summary(self, max_chars: int | None = None) -> str:
        """Возвращает краткую сводку контекста."""
        if max_chars is None:
            max_chars = settings.session_max_context_chars
        if not self.messages:
            return ""
        recent = self.messages[-4:]
        lines = []
        for m in recent:
            prefix = "Пользователь" if m.role == "user" else "Ассистент"
            content = m.content[:200] + "..." if len(m.content) > 200 else m.content
            lines.append(f"{prefix}: {content}")
        summary = "\n".join(lines)
        return summary[:max_chars]


class SessionStore:
    """In-memory хранилище сессий."""

    _instance: ClassVar["SessionStore | None"] = None
    _sessions: ClassVar[dict[str, Session]] = {}

    def __new__(cls) -> "SessionStore":
        """Возвращает singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_or_create(self, session_id: str) -> Session:
        """Получает или создаёт сессию."""
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        """Удаляет сессию."""
        self._sessions.pop(session_id, None)

    def cleanup_old(self, max_age_sec: int | None = None) -> int:
        """Удаляет старые сессии."""
        if max_age_sec is None:
            max_age_sec = settings.session_ttl_sec
        now = time.time()
        to_delete = [sid for sid, s in self._sessions.items() if now - s.created_at > max_age_sec]
        for sid in to_delete:
            del self._sessions[sid]
        return len(to_delete)


def get_session_store() -> SessionStore:
    """Возвращает singleton session store."""
    return SessionStore()
