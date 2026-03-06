"""Schemas for memory co-creation chat."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MemoryChatRequest(BaseModel):
    sessionId: Optional[str] = Field(default=None, description="会话 ID")
    message: str = Field(..., min_length=1, description="用户消息")


class SessionTask(BaseModel):
    question: str
    answerLines: list[str]


class MemoryDraft(BaseModel):
    type: str
    typeLabel: str
    method: str
    methodLabel: str
    keywords: list[str]
    imagery: list[str]
    recap: str


class CardFormat(BaseModel):
    front: str
    back: str


class MemoryCard(BaseModel):
    question: str
    answer: str
    keywords: list[str]
    imagery: list[str]
    recap: str
    cardFormat: CardFormat


class SessionMessage(BaseModel):
    role: Literal["user", "assistant"]
    type: Literal["text", "memory_draft", "memory_question", "memory_revision", "memory_final_card"]
    content: str
    timestamp: int


class MemorySession(BaseModel):
    sessionId: str
    state: Literal["collecting_material", "draft_generated", "revising", "finalized"] = "collecting_material"
    task: Optional[SessionTask] = None
    draft: Optional[MemoryDraft] = None
    history: list[SessionMessage] = Field(default_factory=list)


class MemoryChatResponse(BaseModel):
    sessionId: str
    replyType: Literal["draft", "question", "revision", "final_card"]
    replyText: str
    draft: Optional[MemoryDraft] = None
    finalCard: Optional[MemoryCard] = None

