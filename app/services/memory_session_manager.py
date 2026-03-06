"""In-memory session manager for memory co-creation chat."""

from __future__ import annotations

import time
import uuid

from app.schemas.memory_chat import MemorySession, SessionMessage


class MemorySessionManager:
    def __init__(self):
        self._store: dict[str, MemorySession] = {}

    def get_or_create(self, session_id: str | None = None) -> MemorySession:
        if session_id and session_id in self._store:
            return self._store[session_id]

        new_id = session_id or str(uuid.uuid4())
        session = MemorySession(sessionId=new_id)
        self._store[new_id] = session
        return session

    def save(self, session: MemorySession) -> None:
        self._store[session.sessionId] = session

    @staticmethod
    def make_message(role: str, msg_type: str, content: str) -> SessionMessage:
        return SessionMessage(
            role=role,  # type: ignore[arg-type]
            type=msg_type,  # type: ignore[arg-type]
            content=content,
            timestamp=int(time.time() * 1000),
        )


session_manager = MemorySessionManager()

